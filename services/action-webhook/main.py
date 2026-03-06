import json
import logging
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from typing import Any, Dict

import aiohttp
from fastapi import FastAPI, Request

from actions.device_http import DeviceHttpClient
from actions.slack import SlackNotifier
from config import ActionWebhookConfig, load_action_webhook_config
from rules import RuleEvaluator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("action-webhook")

config: ActionWebhookConfig = load_action_webhook_config()


@asynccontextmanager
async def lifespan(app: FastAPI):
    session = aiohttp.ClientSession()
    app.state.rule_evaluator = RuleEvaluator(
        risk_threshold=config.risk_threshold,
        rules_file=config.rules_file,
    )
    app.state.slack_notifier = SlackNotifier(
        webhook_url=config.slack_webhook_url,
        session=session,
        timeout_sec=config.device_timeout_sec,
    )
    app.state.device_client = DeviceHttpClient(
        endpoint_url=config.device_endpoint_url,
        session=session,
        timeout_sec=config.device_timeout_sec,
    )
    app.state.http_session = session

    logger.info(
        "action-webhook started rules_enabled=%s risk_threshold=%.2f rules_file=%s",
        config.rules_enabled,
        config.risk_threshold,
        config.rules_file,
    )
    try:
        yield
    finally:
        await session.close()


app = FastAPI(title="action-webhook", version="0.2.0", lifespan=lifespan)


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

    matched_rule_ids = []
    actions = []
    action_results: Dict[str, Any] = {}
    derived: Dict[str, Any] = {}

    if config.rules_enabled:
        result = request.app.state.rule_evaluator.evaluate(payload)
        matched_rule_ids = result.matched_rule_ids
        actions = result.actions
        derived = result.derived

        if "slack" in actions:
            action_results["slack"] = await request.app.state.slack_notifier.send(
                payload=payload,
                matched_rule_ids=matched_rule_ids,
            )

        if "device" in actions:
            action_results["device"] = await request.app.state.device_client.post(
                payload=payload,
                matched_rule_ids=matched_rule_ids,
            )

    return {
        "status": "accepted",
        "event_id": event_id,
        "received_at": received_at,
        "rules_enabled": config.rules_enabled,
        "matched_rule_ids": matched_rule_ids,
        "actions": actions,
        "derived": derived,
        "action_results": action_results,
    }
