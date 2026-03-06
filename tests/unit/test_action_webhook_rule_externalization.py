from pathlib import Path
import sys


SERVICE_DIR = Path(__file__).resolve().parents[2] / "services" / "action-webhook"
if str(SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICE_DIR))

from rules import RuleEvaluator  # noqa: E402


def test_config_driven_rule_order_and_actions():
    evaluator = RuleEvaluator(
        risk_threshold=0.75,
        rule_definitions=[
            {
                "id": "custom_keyword",
                "enabled": True,
                "when": {"text_contains_any": ["DANGER"]},
                "actions": ["slack"],
            },
            {
                "id": "custom_yes",
                "enabled": True,
                "when": {"answer_in": ["yes"]},
                "actions": ["device"],
            },
        ],
    )

    result = evaluator.evaluate({"text": "yes DANGER detected"})

    assert result.matched_rule_ids == ["custom_keyword", "custom_yes"]
    assert result.actions == ["slack", "device"]


def test_disabled_rule_is_not_applied():
    evaluator = RuleEvaluator(
        risk_threshold=0.75,
        rule_definitions=[
            {
                "id": "disabled_rule",
                "enabled": False,
                "when": {"answer_in": ["yes"]},
                "actions": ["slack", "device"],
            }
        ],
    )

    result = evaluator.evaluate({"text": "yes"})

    assert result.matched_rule_ids == []
    assert result.actions == []


def test_risk_threshold_placeholder_uses_runtime_value():
    evaluator = RuleEvaluator(
        risk_threshold=0.82,
        rule_definitions=[
            {
                "id": "risk_rule",
                "enabled": True,
                "when": {"risk_score_gte": "${RISK_THRESHOLD}"},
                "actions": ["slack"],
            }
        ],
    )

    low = evaluator.evaluate({"text": "{}", "risk_score": 0.81})
    high = evaluator.evaluate({"text": "{}", "risk_score": 0.82})

    assert low.matched_rule_ids == []
    assert high.matched_rule_ids == ["risk_rule"]
