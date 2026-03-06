from dataclasses import dataclass
import json
import re
from typing import Any, Dict, List, Mapping, Optional, Set


YES_NO_PATTERN = re.compile(r"\b(yes|no)\b", re.IGNORECASE)


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

    def __init__(self, risk_threshold: float = 0.75):
        self._risk_threshold = risk_threshold
        self._keywords = ("ALERT", "WARNING", "CAUTION")

    def evaluate(self, payload: Mapping[str, Any]) -> EvaluationResult:
        text = str(payload.get("text", "") or "")
        text_upper = text.upper()
        text_json = self._parse_json_text(text)

        answer = self._extract_answer(payload, text, text_json)
        risk_score = self._extract_risk_score(payload, text_json)

        matched_rule_ids: List[str] = []
        action_set: Set[str] = set()

        if answer == "yes":
            matched_rule_ids.append("rule_yes")
            action_set.update(("slack", "device"))
        if answer == "no":
            matched_rule_ids.append("rule_no")
            action_set.add("slack")
        if any(keyword in text_upper for keyword in self._keywords):
            matched_rule_ids.append("rule_keyword_alert")
            action_set.add("slack")
        if risk_score is not None and risk_score >= self._risk_threshold:
            matched_rule_ids.append("rule_risk_high")
            action_set.add("slack")

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
        text_json: Optional[Mapping[str, Any]],
    ) -> Optional[float]:
        risk_value = payload.get("risk_score")
        if risk_value is None and text_json is not None:
            risk_value = text_json.get("risk_score")
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
