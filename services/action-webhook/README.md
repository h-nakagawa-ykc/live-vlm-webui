# action-webhook (MVP)

`action-webhook` は `live-vlm-webui` から送信される webhook payload を受信し、
ルール評価結果に応じて Slack 通知や HTTP 機器連携を実行するデモ向けマイクロサービス。

## Endpoints
- `GET /healthz` : プロセス生存確認
- `POST /events` : webhook payload 受信、ルール評価、アクション実行

## Main Config (Env)
- `ACTION_RULES_ENABLED` : ルール評価の有効化
- `ACTION_RULES_FILE` : ルール定義ファイルパス（コンテナ内例: `/app/rule_configs/rules.yaml`）
- `RISK_THRESHOLD` : `risk_score_gte` 判定閾値
- `SLACK_WEBHOOK_URL` : Slack Incoming Webhook URL
- `DEVICE_ENDPOINT_URL` : HTTP制御対象機器のエンドポイント
- `DEVICE_TIMEOUT_SEC` : 外部連携呼び出しタイムアウト秒

## Related Docs
- 手動検証ガイド: `../../docs/development/action-webhook-manual-test-ja.md`
- payload仕様: `../../docs/development/webhook-events.md`
- 実装ロードマップ: `../../docs/development/action-orchestration-roadmap-ja.md`
