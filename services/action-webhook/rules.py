from dataclasses import dataclass
import json
import logging
from pathlib import Path
import re
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set

try:
    import yaml
except Exception:  # pragma: no cover - optional dependency fallback
    yaml = None


YES_NO_PATTERN = re.compile(r"\b(yes|no)\b", re.IGNORECASE)
logger = logging.getLogger("action-webhook.rules")


@dataclass
class EvaluationResult:
    matched_rule_ids: List[str]
    actions: List[str]
    derived: Dict[str, Any]


class RuleEvaluator:
    """
    Fixed-rule evaluator for MVP.

    Rule-A: answer == yes -> slack + device
    Rule-B: answer == no -> slack
    Rule-C: text contains ALERT/WARNING/CAUTION -> slack
    Rule-D: risk_score >= threshold -> slack
    """

    def __init__(
        self,
        risk_threshold: float = 0.75,
        rules_file: Optional[str] = None,
        rule_definitions: Optional[List[Dict[str, Any]]] = None,
    ):
        self._risk_threshold = risk_threshold
        self._rules = rule_definitions if rule_definitions is not None else self._load_rules(rules_file)

    def evaluate(self, payload: Mapping[str, Any]) -> EvaluationResult:
        text = str(payload.get("text", "") or "")
        text_upper = text.upper()
        text_json = self._parse_json_text(text)

        # debug for Json check
        logger.debug("@payload: %s.", payload)
        logger.debug("@text: %s.", text)
        logger.debug("@text_upper: %s.", text_upper)
        logger.debug("@text_json: %s.", text_json)

        answer = self._extract_answer(payload, text, text_json)
        risk_score = self._extract_risk_score(payload, text, text_json)

        matched_rule_ids: List[str] = []
        action_set: Set[str] = set()

        # debug for Json check
        logger.debug("@answer: %s.", answer)
        logger.debug("@risk_score: %s.", risk_score)
        context = {
            "answer": answer,
            "risk_score": risk_score,
            "text": text,
            "text_upper": text_upper,
        }

        for rule in self._rules:
            if not self._rule_matches(rule, context):
                continue
            matched_rule_ids.append(str(rule.get("id", "unknown_rule")))
            for action in rule.get("actions", []):
                action_set.add(str(action))

        actions = [name for name in ("slack", "device") if name in action_set]
        return EvaluationResult(
            matched_rule_ids=matched_rule_ids,
            actions=actions,
            derived={"answer": answer, "risk_score": risk_score},
        )

    def _extract_answer(
        self,
        payload: Mapping[str, Any],
        text: str,
        text_json: Optional[Mapping[str, Any]],
    ) -> Optional[str]:
        answer_raw = payload.get("answer")
        if answer_raw is None and text_json is not None:
            answer_raw = text_json.get("answer")
        if answer_raw is not None:
            answer = str(answer_raw).strip().lower()
            if answer in {"yes", "no", "unknown"}:
                return answer

        match = YES_NO_PATTERN.search(text)
        if match:
            return match.group(1).lower()
        return None

    def _extract_risk_score(
        self,
        payload: Mapping[str, Any],
        text: str,
        text_json: Optional[Mapping[str, Any]],
    ) -> Optional[float]:
        risk_value = payload.get("risk_score")
        if risk_value is None and text_json is not None:
            risk_value = text_json.get("risk_score")
        if risk_value is None:
            # text='risk_score: 0.XX'、text='{ "risk_score: 0.XX" }'等を想定し、'risk_score'と'<数値>'の2個の文字列グループに分割
            match = re.search(r"([\s|\"]*risk_score[\s|\"]*:\D*)(\d*.\d*)", text, re.DOTALL)
            logger.debug("@--match: %s.", match)
            if match:
                # 文字列グループ(タプル)の2番目に`<数値>`が格納されている想定
                risk_value = match.groups()[1]
        if risk_value is None:
            return None
        try:
            value = float(risk_value)
        except (TypeError, ValueError):
            return None
        if value < 0 or value > 1:
            return None
        return value

    def _parse_json_text(self, text: str) -> Optional[Mapping[str, Any]]:
        if not text:
            return None
        stripped = text.strip()
        if not stripped.startswith("{"):
            return None
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            return None
        if isinstance(parsed, dict):
            return parsed
        return None

    def _load_rules(self, rules_file: Optional[str]) -> List[Dict[str, Any]]:
        if not rules_file:
            return self._default_rules()

        path = Path(rules_file)
        if not path.is_absolute():
            path = Path(__file__).resolve().parent / path

        if not path.exists():
            logger.warning("Rules file not found: %s. Falling back to defaults.", path)
            return self._default_rules()

        if yaml is None:
            logger.warning("PyYAML not available. Falling back to default rules.")
            return self._default_rules()

        try:
            with path.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except Exception as exc:
            logger.warning("Failed to load rules file %s (%s). Using defaults.", path, exc)
            return self._default_rules()

        rules = data.get("rules")
        if not isinstance(rules, list):
            logger.warning("Invalid rules schema in %s. Using defaults.", path)
            return self._default_rules()

        validated = []
        for idx, rule in enumerate(rules):
            if not isinstance(rule, dict):
                logger.warning("Skipping non-dict rule at index %d", idx)
                continue
            if "id" not in rule or "actions" not in rule or "when" not in rule:
                logger.warning("Skipping incomplete rule at index %d", idx)
                continue
            validated.append(rule)

        return validated or self._default_rules()

    def _rule_matches(self, rule: Mapping[str, Any], context: Mapping[str, Any]) -> bool:
        if not bool(rule.get("enabled", True)):
            return False
        when = rule.get("when", {})
        if not isinstance(when, Mapping):
            return False

        answer_in = when.get("answer_in")
        if answer_in is not None:
            if not self._match_answer_in(answer_in, context.get("answer")):
                return False

        text_contains_any = when.get("text_contains_any")
        if text_contains_any is not None:
            if not self._match_text_contains_any(text_contains_any, context.get("text_upper")):
                return False

        risk_score_gte = when.get("risk_score_gte")
        if risk_score_gte is not None:
            if not self._match_risk_score_gte(risk_score_gte, context.get("risk_score")):
                return False

        return True

    @staticmethod
    def _match_answer_in(values: Any, answer: Any) -> bool:
        if answer is None:
            return False
        if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
            return False
        allowed = {str(v).strip().lower() for v in values}
        return str(answer).strip().lower() in allowed

    @staticmethod
    def _match_text_contains_any(values: Any, text_upper: Any) -> bool:
        if not text_upper or not isinstance(text_upper, str):
            return False
        if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
            return False
        return any(str(v).upper() in text_upper for v in values)

    def _match_risk_score_gte(self, threshold_raw: Any, risk_score: Any) -> bool:
        if risk_score is None:
            return False

        threshold = self._resolve_threshold(threshold_raw)
        if threshold is None:
            return False
        try:
            return float(risk_score) >= threshold
        except (TypeError, ValueError):
            return False

    def _resolve_threshold(self, threshold_raw: Any) -> Optional[float]:
        if isinstance(threshold_raw, str) and threshold_raw.strip() == "${RISK_THRESHOLD}":
            return self._risk_threshold
        try:
            return float(threshold_raw)
        except (TypeError, ValueError):
            return None

    def _default_rules(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": "rule_yes",
                "enabled": True,
                "when": {"answer_in": ["yes"]},
                "actions": ["slack", "device"],
            },
            {
                "id": "rule_no",
                "enabled": True,
                "when": {"answer_in": ["no"]},
                "actions": ["slack"],
            },
            {
                "id": "rule_keyword_alert",
                "enabled": True,
                "when": {"text_contains_any": ["ALERT", "WARNING", "CAUTION"]},
                "actions": ["slack"],
            },
            {
                "id": "rule_risk_high",
                "enabled": True,
                "when": {"risk_score_gte": "${RISK_THRESHOLD}"},
                "actions": ["slack"],
            },
        ]
