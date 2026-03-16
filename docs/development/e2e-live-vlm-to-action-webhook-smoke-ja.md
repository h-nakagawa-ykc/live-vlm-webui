# E2Eスモーク手順: live-vlm-webui -> action-webhook

## 目的
- デモ前の最終確認として、`action-webhook` の受信・判定動作を短時間で検証する。
- `yes/no`, `keyword`, `risk_score` の3系統ルールが想定どおり動作することを確認する。

## この手順で確認できること
- `action-webhook` コンテナ起動
- `/healthz` 応答
- `/events` に対するルール判定結果（`matched_rule_ids`, `actions`）

## この手順で確認しないこと
- カメラ入力からの実推論結果（WebRTC/RTSP経由）
- 実Slack通知・実機器制御の到達

上記は本手順の後に、手動スモークで確認する。

## 前提
- Docker / Docker Compose が利用可能
- リポジトリルート: `live-vlm-webui/`

## 実行コマンド
```bash
cd live-vlm-webui
bash scripts/run_e2e_live_vlm_action_webhook_smoke.sh
```

## 期待結果
- 最後に `SUCCESS: action-webhook E2E smoke checks passed.` が表示される
- 実行中に以下3ケースが `OK` になる
  - `rule_yes` + `slack,device`
  - `rule_keyword_alert` + `slack`
  - `rule_risk_high` + `slack`

## オプション
- `live-vlm-webui` も同時起動:
```bash
START_LIVE_VLM=1 bash scripts/run_e2e_live_vlm_action_webhook_smoke.sh
```

- action-webhook URLを変更:
```bash
ACTION_WEBHOOK_URL=http://127.0.0.1:8081 bash scripts/run_e2e_live_vlm_action_webhook_smoke.sh
```

- composeファイルを変更:
```bash
COMPOSE_FILE=docker/docker-compose.override.yml bash scripts/run_e2e_live_vlm_action_webhook_smoke.sh
```

## 実Slack/実機器の手動確認
1. `.env` へ `SLACK_WEBHOOK_URL` と `DEVICE_ENDPOINT_URL` を設定
2. `action-webhook` を再起動
3. `curl` で `yes` / `keyword` / `risk_score` payload を送信
4. Slack着信、機器動作を確認

参考: `docs/development/action-webhook-manual-test-ja.md`

## 失敗時の切り分け
1. `healthz` がNG
```bash
docker compose -f docker/docker-compose.override.yml logs --tail=200 action-webhook
```
2. `/events` で期待ルールに一致しない
- `ACTION_RULES_ENABLED=1` か確認
- `ACTION_RULES_FILE=/app/rule_configs/rules.yaml` か確認
3. 期待アクションが出ない
- ルール定義: `services/action-webhook/rule_configs/rules.yaml`
- 評価ロジック: `services/action-webhook/rules.py`

