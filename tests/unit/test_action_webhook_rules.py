from pathlib import Path
import sys


SERVICE_DIR = Path(__file__).resolve().parents[2] / "services" / "action-webhook"
if str(SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICE_DIR))

from rules import RuleEvaluator  # noqa: E402


def test_rule_yes_triggers_slack_and_device():
    evaluator = RuleEvaluator(risk_threshold=0.75)

    result = evaluator.evaluate({"text": "Yes, person is in danger"})

    assert result.matched_rule_ids == ["rule_yes"]
    assert result.actions == ["slack", "device"]
    assert result.derived["answer"] == "yes"
    assert result.derived["risk_score"] is None


def test_rule_no_triggers_slack_only_from_json_text():
    evaluator = RuleEvaluator(risk_threshold=0.75)

    result = evaluator.evaluate({"text": '{"answer":"no","risk_score":0.22}'})

    assert result.matched_rule_ids == ["rule_no"]
    assert result.actions == ["slack"]
    assert result.derived["answer"] == "no"
    assert result.derived["risk_score"] == 0.22


def test_keyword_rule_triggers_slack():
    evaluator = RuleEvaluator(risk_threshold=0.75)

    result = evaluator.evaluate({"text": "WARNING: smoke detected near panel"})

    assert result.matched_rule_ids == ["rule_keyword_alert"]
    assert result.actions == ["slack"]
    assert result.derived["answer"] is None


def test_risk_rule_triggers_slack_with_payload_field():
    evaluator = RuleEvaluator(risk_threshold=0.75)

    result = evaluator.evaluate({"text": "unknown", "risk_score": 0.91})

    assert result.matched_rule_ids == ["rule_risk_high"]
    assert result.actions == ["slack"]
    assert result.derived["risk_score"] == 0.91


def test_multiple_rule_matches_dedupe_actions():
    evaluator = RuleEvaluator(risk_threshold=0.75)

    result = evaluator.evaluate(
        {"text": "yes ALERT: escalation required", "risk_score": 0.90}
    )

    assert result.matched_rule_ids == ["rule_yes", "rule_keyword_alert", "rule_risk_high"]
    assert result.actions == ["slack", "device"]


def test_out_of_range_risk_score_is_ignored():
    evaluator = RuleEvaluator(risk_threshold=0.75)

    result = evaluator.evaluate({"text": "ALERT", "risk_score": 1.5})

    assert result.matched_rule_ids == ["rule_keyword_alert"]
    assert result.actions == ["slack"]
    assert result.derived["risk_score"] is None
