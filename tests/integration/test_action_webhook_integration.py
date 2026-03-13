from dataclasses import dataclass
import importlib.util
from pathlib import Path
import sys

from fastapi.testclient import TestClient


SERVICE_DIR = Path(__file__).resolve().parents[2] / "services" / "action-webhook"
MAIN_PATH = SERVICE_DIR / "main.py"

if str(SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICE_DIR))


def _load_action_webhook_main():
    spec = importlib.util.spec_from_file_location("action_webhook_main", MAIN_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_test_client(app):
    return TestClient(app)


@dataclass
class _FakeEvaluationResult:
    matched_rule_ids: list[str]
    actions: list[str]
    derived: dict


class _FakeRuleEvaluator:
    def evaluate(self, payload):
        _ = payload
        return _FakeEvaluationResult(
            matched_rule_ids=["rule_yes"],
            actions=["slack", "device"],
            derived={"answer": "yes", "risk_score": 0.91},
        )


class _FakeSlackNotifier:
    async def send(self, payload, matched_rule_ids):
        _ = payload, matched_rule_ids
        return {"status": "sent", "http_status": 200}


class _FakeDeviceClient:
    async def post(self, payload, matched_rule_ids):
        _ = payload, matched_rule_ids
        return {"status": "sent", "http_status": 200}


class _FakeSlackNotifierFailed:
    async def send(self, payload, matched_rule_ids):
        _ = payload, matched_rule_ids
        return {"status": "failed", "detail": "mock slack failure"}


class _FakeDeviceClientFailed:
    async def post(self, payload, matched_rule_ids):
        _ = payload, matched_rule_ids
        return {"status": "failed", "detail": "mock device failure"}


def test_healthz_returns_ok():
    module = _load_action_webhook_main()

    with _create_test_client(module.app) as client:
        resp = client.get("/healthz")

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_events_flow_uses_evaluator_output_and_executes_actions():
    module = _load_action_webhook_main()
    module.config.rules_enabled = True

    with _create_test_client(module.app) as client:
        client.app.state.rule_evaluator = _FakeRuleEvaluator()
        client.app.state.slack_notifier = _FakeSlackNotifier()
        client.app.state.device_client = _FakeDeviceClient()

        resp = client.post(
            "/events",
            json={
                "event_id": "it-001",
                "event_type": "vlm_inference_result",
                "mode": "single",
                "text": "yes",
            },
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "accepted"
    assert body["event_id"] == "it-001"
    assert body["matched_rule_ids"] == ["rule_yes"]
    assert body["actions"] == ["slack", "device"]
    assert body["derived"]["answer"] == "yes"
    assert body["action_results"]["slack"]["status"] == "sent"
    assert body["action_results"]["device"]["status"] == "sent"


def test_events_with_rules_disabled_skips_action_execution():
    module = _load_action_webhook_main()
    module.config.rules_enabled = False

    with _create_test_client(module.app) as client:
        resp = client.post(
            "/events",
            json={
                "event_id": "it-002",
                "event_type": "vlm_inference_result",
                "mode": "single",
                "text": "ALERT",
            },
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "accepted"
    assert body["matched_rule_ids"] == []
    assert body["actions"] == []
    assert body["action_results"] == {}


def test_events_slack_failure_is_non_fatal():
    module = _load_action_webhook_main()
    module.config.rules_enabled = True

    with _create_test_client(module.app) as client:
        client.app.state.rule_evaluator = _FakeRuleEvaluator()
        client.app.state.slack_notifier = _FakeSlackNotifierFailed()
        client.app.state.device_client = _FakeDeviceClient()

        resp = client.post(
            "/events",
            json={
                "event_id": "it-003",
                "event_type": "vlm_inference_result",
                "mode": "single",
                "text": "yes",
            },
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "accepted"
    assert body["matched_rule_ids"] == ["rule_yes"]
    assert body["actions"] == ["slack", "device"]
    assert body["action_results"]["slack"]["status"] == "failed"
    assert body["action_results"]["device"]["status"] == "sent"


def test_events_device_failure_is_non_fatal():
    module = _load_action_webhook_main()
    module.config.rules_enabled = True

    with _create_test_client(module.app) as client:
        client.app.state.rule_evaluator = _FakeRuleEvaluator()
        client.app.state.slack_notifier = _FakeSlackNotifier()
        client.app.state.device_client = _FakeDeviceClientFailed()

        resp = client.post(
            "/events",
            json={
                "event_id": "it-004",
                "event_type": "vlm_inference_result",
                "mode": "single",
                "text": "yes",
            },
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "accepted"
    assert body["matched_rule_ids"] == ["rule_yes"]
    assert body["actions"] == ["slack", "device"]
    assert body["action_results"]["slack"]["status"] == "sent"
    assert body["action_results"]["device"]["status"] == "failed"
