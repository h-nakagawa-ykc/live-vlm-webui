# PR-5: action-webhook 統合テストケース一覧（MVP）

## 目的
- `POST /events` の受信から、ルール評価・アクション実行・レスポンス生成までの結合動作を確認する。
- 本PRでは「外部依存をモック化した統合テスト」を先行し、実Slack/実機器連携は手動スモークテストで補完する。

## 対象コンポーネント
- `services/action-webhook/main.py`
- `services/action-webhook/rules.py`
- `services/action-webhook/actions/slack.py`
- `services/action-webhook/actions/device_http.py`

## テスト方針
- 自動テスト: モックベース（CI向け、再現性重視）
- 手動テスト: 実Webhook URL / 実機器エンドポイント（デモ前最終確認）

## 自動テストケース（PR-5で先に実装）

1. `GET /healthz` 正常応答
- 入力: なし
- 期待: `200`, `{"status":"ok"}`

2. `POST /events` で rule evaluator の結果がレスポンスへ反映される
- 入力: `event_id`, `event_type`, `mode`, `text` を含むpayload
- 前提: evaluatorをモックし `matched_rule_ids=["rule_yes"]`, `actions=["slack","device"]` を返す
- 期待:
  - `status="accepted"`
  - `matched_rule_ids` と `actions` がモック結果と一致
  - `action_results.slack` / `action_results.device` が返る

3. `ACTION_RULES_ENABLED=false` 時はアクション非実行
- 入力: 任意payload
- 前提: `config.rules_enabled=False`
- 期待:
  - `matched_rule_ids=[]`
  - `actions=[]`
  - `action_results={}`

## 追加候補（PR-5後半またはPR-6）

4. Slack失敗が非致命であること
- 前提: Slack通知モックが例外/失敗を返す
- 期待: `/events` は `200 accepted` 継続、device側は実行可能

5. Device失敗が非致命であること
- 前提: Device通知モックが例外/失敗を返す
- 期待: `/events` は `200 accepted` 継続、Slack側は実行可能

6. フォールバック動作（`ACTION_RULES_FILE` 不正/未存在）
- 前提: 起動設定で不正パスを指定
- 期待: デフォルトルールへフォールバックし判定継続

## 手動スモークテスト（実サービス接続）

1. Slack通知確認
- Slack Incoming Webhook URL を `SLACK_WEBHOOK_URL` に設定
- `rule_yes` などで通知発火し、テストチャンネルにメッセージ到達すること

2. IP機器制御確認
- `DEVICE_ENDPOINT_URL` を実機器のHTTP制御エンドポイントに設定
- `rule_yes` などでPOSTが送信され、機器側アクションが発生すること

## 実行例
```bash
pytest tests/integration/test_action_webhook_integration.py -v
```

補足:
- テスト環境に `fastapi` が無い場合は当該テストを skip する設計にする。
- 実Slack/実機器を使う試験はCIではなく手動実施を推奨する。

