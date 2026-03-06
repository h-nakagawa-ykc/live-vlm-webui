import logging
from typing import Any, Dict, List, Mapping

import aiohttp

logger = logging.getLogger("action-webhook.device")


class DeviceHttpClient:
    def __init__(
        self,
        endpoint_url: str,
        session: aiohttp.ClientSession,
        timeout_sec: float = 2.0,
    ):
        self._endpoint_url = endpoint_url
        self._session = session
        self._timeout_sec = timeout_sec

    async def post(self, payload: Mapping[str, Any], matched_rule_ids: List[str]) -> Dict[str, Any]:
        if not self._endpoint_url:
            return {"status": "skipped", "reason": "DEVICE_ENDPOINT_URL is empty"}

        body = {
            "event_id": payload.get("event_id"),
            "event_type": payload.get("event_type"),
            "mode": payload.get("mode"),
            "matched_rule_ids": matched_rule_ids,
            "payload": payload,
        }

        try:
            timeout = aiohttp.ClientTimeout(total=self._timeout_sec)
            async with self._session.post(self._endpoint_url, json=body, timeout=timeout) as resp:
                if 200 <= resp.status < 300:
                    return {"status": "sent", "http_status": resp.status}
                detail = (await resp.text())[:400]
                logger.warning("Device request failed status=%s body=%s", resp.status, detail)
                return {"status": "failed", "http_status": resp.status, "detail": detail}
        except Exception as exc:  # non-fatal by design
            logger.error("Device request error: %s", exc)
            return {"status": "failed", "detail": str(exc)}
