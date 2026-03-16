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

### オプションの意図と挙動
1. `START_LIVE_VLM=1`
- 目的: `action-webhook` 単体確認に加えて、`live-vlm-webui` コンテナの起動疎通も同時に確認する。
- 変化: スクリプト内で `live-vlm-webui` の `docker compose up` を追加実行する。
- 注意: このオプションを有効にしても、カメラ入力からの実推論まで自動検証するわけではない。

2. `ACTION_WEBHOOK_URL=...`
- 目的: `action-webhook` の接続先を切り替える（別ホスト、ポート変更、リバースプロキシ配下など）。
- 変化: `healthz` と `/events` の送信先URLが指定値に変わる。
- 想定例: `http://127.0.0.1:8081`、`http://action-webhook:8081`（同一ネットワーク内）。

3. `COMPOSE_FILE=...`
- 目的: 使用する compose 定義を切り替える（環境別の定義、実験用定義）。
- 変化: スクリプトが `docker compose -f <指定ファイル>` でサービスを起動する。
- 想定例: 標準の `docker/docker-compose.override.yml` 以外の compose ファイル検証。

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
