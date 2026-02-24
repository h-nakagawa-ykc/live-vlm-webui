"""
Asynchronous webhook event dispatcher.

Design goals:
- Do not break existing VLM processing if webhook delivery fails.
- Keep API minimal so it can be wired from single/multi inference paths later.
"""

from dataclasses import dataclass
from typing import Any, Mapping, Optional
import logging
import time
import uuid

import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class EventDispatcherConfig:
    enabled: bool = False
    url: str = ""
    timeout_sec: float = 2.0
    mode: str = "both"  # single|multi|both
    sample_every: int = 1
    include_metrics: bool = True


class EventDispatcher:
    """Send webhook events asynchronously without raising fatal errors upstream."""

    def __init__(
        self,
        config: EventDispatcherConfig,
        session: Optional[aiohttp.ClientSession] = None,
    ):
        self.config = config
        self._session = session
        self._owned_session = False
        self._counter = 0

    async def close(self) -> None:
        if self._owned_session and self._session and not self._session.closed:
            await self._session.close()

    async def dispatch(self, payload: Mapping[str, Any], mode: str = "both") -> bool:
        """
        Attempt to send one event.

        Returns:
            True if event was delivered.
            False if skipped/failed.
        """
        if not self.config.enabled:
            return False
        if not self.config.url:
            logger.warning("Event dispatcher enabled but URL is empty; skipping dispatch")
            return False
        if self.config.mode not in {"single", "multi", "both"}:
            logger.warning("Invalid dispatcher mode=%s; skipping dispatch", self.config.mode)
            return False
        if self.config.mode != "both" and self.config.mode != mode:
            return False

        self._counter += 1
        if self.config.sample_every > 1 and (self._counter % self.config.sample_every) != 0:
            return False

        event_id = str(uuid.uuid4())
        body = dict(payload)
        body.setdefault("event_id", event_id)
        body.setdefault("event_type", "vlm_inference_result")
        body.setdefault("timestamp_unix", time.time())

        timeout = aiohttp.ClientTimeout(total=self.config.timeout_sec)
        session = await self._get_session(timeout)

        try:
            async with session.post(self.config.url, json=body) as resp:
                if 200 <= resp.status < 300:
                    logger.info("Webhook delivered (event_id=%s status=%s)", event_id, resp.status)
                    return True

                text = await resp.text()
                logger.warning(
                    "Webhook failed (event_id=%s status=%s body=%s)",
                    event_id,
                    resp.status,
                    text[:300],
                )
                return False
        except Exception as e:
            # Intentionally non-fatal: dispatch failure must not stop VLM processing.
            logger.error("Webhook error (event_id=%s): %s", event_id, e)
            return False

    async def _get_session(self, timeout: aiohttp.ClientTimeout) -> aiohttp.ClientSession:
        if self._session is not None and not self._session.closed:
            return self._session
        self._session = aiohttp.ClientSession(timeout=timeout)
        self._owned_session = True
        return self._session
