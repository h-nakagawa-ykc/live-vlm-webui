import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import FastAPI, Request

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("action-webhook")

app = FastAPI(title="action-webhook", version="0.1.0")


@app.get("/healthz")
async def healthz() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/events")
async def events(request: Request) -> Dict[str, Any]:
    payload = await request.json()
    event_id = payload.get("event_id", "unknown")
    mode = payload.get("mode", "unknown")
    event_type = payload.get("event_type", "unknown")
    received_at = datetime.now(timezone.utc).isoformat()

    logger.info(
        "Received webhook event: id=%s type=%s mode=%s payload=%s",
        event_id,
        event_type,
        mode,
        json.dumps(payload, ensure_ascii=True),
    )

    return {
        "status": "accepted",
        "event_id": event_id,
        "received_at": received_at,
    }
