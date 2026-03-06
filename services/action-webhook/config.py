from dataclasses import dataclass
import os


@dataclass
class ActionWebhookConfig:
    rules_enabled: bool = False
    slack_webhook_url: str = ""
    device_endpoint_url: str = ""
    device_timeout_sec: float = 2.0
    risk_threshold: float = 0.75


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def load_action_webhook_config() -> ActionWebhookConfig:
    device_timeout_sec = _env_float("DEVICE_TIMEOUT_SEC", 2.0)
    if device_timeout_sec <= 0:
        device_timeout_sec = 2.0

    risk_threshold = _env_float("RISK_THRESHOLD", 0.75)
    if risk_threshold < 0:
        risk_threshold = 0.0
    if risk_threshold > 1:
        risk_threshold = 1.0

    return ActionWebhookConfig(
        rules_enabled=_env_bool("ACTION_RULES_ENABLED", False),
        slack_webhook_url=os.getenv("SLACK_WEBHOOK_URL", "").strip(),
        device_endpoint_url=os.getenv("DEVICE_ENDPOINT_URL", "").strip(),
        device_timeout_sec=device_timeout_sec,
        risk_threshold=risk_threshold,
    )
