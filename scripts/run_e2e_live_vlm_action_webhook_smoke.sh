#!/usr/bin/env bash
set -euo pipefail

# E2E smoke for action-webhook path.
# - Starts action-webhook container
# - Sends representative payloads to /events
# - Verifies matched_rule_ids/actions in response
#
# NOTE:
# This script validates receiver behavior with synthetic payloads.
# For full camera/WebRTC inference flow, see the companion doc.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-docker/docker-compose.override.yml}"
ACTION_WEBHOOK_URL="${ACTION_WEBHOOK_URL:-http://localhost:8081}"
START_LIVE_VLM="${START_LIVE_VLM:-0}" # Set 1 to also start live-vlm-webui.

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "ERROR: required command not found: $1" >&2
    exit 1
  }
}

wait_healthz() {
  local url="$1"
  local retries=40
  local i
  for i in $(seq 1 "$retries"); do
    if curl -fsS "$url/healthz" >/dev/null 2>&1; then
      echo "healthz OK: $url"
      return 0
    fi
    sleep 1
  done
  echo "ERROR: healthz check failed: $url" >&2
  return 1
}

assert_event_response() {
  local response_json="$1"
  local expected_rule="$2"
  local expected_actions_csv="$3"

  python3 - "$response_json" "$expected_rule" "$expected_actions_csv" <<'PY'
import json
import sys

body = json.loads(sys.argv[1])
expected_rule = sys.argv[2]
expected_actions = [x for x in sys.argv[3].split(",") if x]

if body.get("status") != "accepted":
    raise SystemExit(f"status is not accepted: {body}")

rules = body.get("matched_rule_ids", [])
if expected_rule and expected_rule not in rules:
    raise SystemExit(f"expected rule not found: {expected_rule}, got={rules}")

actions = body.get("actions", [])
for action in expected_actions:
    if action not in actions:
        raise SystemExit(f"expected action not found: {action}, got={actions}")

print(f"OK: rules={rules}, actions={actions}")
PY
}

post_event() {
  local payload="$1"
  curl -fsS -X POST "$ACTION_WEBHOOK_URL/events" \
    -H "Content-Type: application/json" \
    -d "$payload"
}

main() {
  require_cmd docker
  require_cmd curl
  require_cmd python3

  cd "$ROOT_DIR"

  if [[ ! -f "$COMPOSE_FILE" ]]; then
    echo "ERROR: compose file not found: $COMPOSE_FILE" >&2
    exit 1
  fi

  echo "[1/5] Starting action-webhook..."
  ACTION_RULES_ENABLED=1 \
  ACTION_RULES_FILE=/app/rule_configs/rules.yaml \
  SLACK_WEBHOOK_URL= \
  DEVICE_ENDPOINT_URL= \
  DEVICE_TIMEOUT_SEC=1 \
  RISK_THRESHOLD=0.75 \
  docker compose -f "$COMPOSE_FILE" up -d --build action-webhook

  if [[ "$START_LIVE_VLM" == "1" ]]; then
    echo "[optional] Starting live-vlm-webui..."
    docker compose -f "$COMPOSE_FILE" up -d --build --no-deps live-vlm-webui
  fi

  echo "[2/5] Waiting for healthz..."
  wait_healthz "$ACTION_WEBHOOK_URL"

  echo "[3/5] yes/no scenario"
  resp="$(post_event '{
    "event_id":"smoke-yes-001",
    "event_type":"vlm_inference_result",
    "mode":"single",
    "text":"normal",
    "answer":"yes"
  }')"
  assert_event_response "$resp" "rule_yes" "slack,device"

  echo "[4/5] keyword scenario"
  resp="$(post_event '{
    "event_id":"smoke-keyword-001",
    "event_type":"vlm_inference_result",
    "mode":"single",
    "text":"WARNING: smoke near panel"
  }')"
  assert_event_response "$resp" "rule_keyword_alert" "slack"

  echo "[5/5] risk_score scenario"
  resp="$(post_event '{
    "event_id":"smoke-risk-001",
    "event_type":"vlm_inference_result",
    "mode":"single",
    "text":"normal",
    "risk_score":0.91
  }')"
  assert_event_response "$resp" "rule_risk_high" "slack"

  echo "SUCCESS: action-webhook E2E smoke checks passed."
  echo "Tip: docker compose -f $COMPOSE_FILE logs --tail=100 action-webhook"
}

main "$@"

