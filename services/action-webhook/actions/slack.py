import json
import logging
from typing import Any, Dict, List, Mapping

import aiohttp

logger = logging.getLogger("action-webhook.slack")


class SlackNotifier:
    def __init__(
        self,
        webhook_url: str,
        session: aiohttp.ClientSession,
        timeout_sec: float = 2.0,
    ):
        self._webhook_url = webhook_url
        self._session = session
        self._timeout_sec = timeout_sec

    async def send(self, payload: Mapping[str, Any], matched_rule_ids: List[str]) -> Dict[str, Any]:
        if not self._webhook_url:
            return {"status": "skipped", "reason": "SLACK_WEBHOOK_URL is empty"}

        event_id = str(payload.get("event_id", "unknown"))
        mode = str(payload.get("mode", "unknown"))
        text = str(payload.get("text", "") or "")

        message = (
            f"[live-vlm] event_id={event_id} mode={mode} "
            f"rules={','.join(matched_rule_ids) or 'none'} text={text[:300]}"
        )

        body = {
            "text": message,
            "attachments": [
                {
                    "color": "#d32f2f",
                    "title": "VLM Event",
                    "text": json.dumps(payload, ensure_ascii=False)[:2000],
                }
            ],
        }

        try:
            timeout = aiohttp.ClientTimeout(total=self._timeout_sec)
            async with self._session.post(self._webhook_url, json=body, timeout=timeout) as resp:
                if 200 <= resp.status < 300:
                    return {"status": "sent", "http_status": resp.status}
                detail = (await resp.text())[:400]
                logger.warning("Slack notification failed status=%s body=%s", resp.status, detail)
                return {"status": "failed", "http_status": resp.status, "detail": detail}
        except Exception as exc:  # non-fatal by design
            logger.error("Slack notification error: %s", exc)
            return {"status": "failed", "detail": str(exc)}
