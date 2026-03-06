# Action Orchestration 開発方針（MVP〜拡張）

## 1. 目的
- 現在の `live-vlm-webui`（マルチフレーム推論 + Webhook送信）を基盤に、**VLM応答に応じて外部アクションを起動**する。
- まずは **実装スピード重視** で、短期間でデモインパクトが出る構成を作る。
- 将来的に RTSP監視・通知・機器制御・Physical AI 連携へ段階的に発展できる設計にする。

## 2. 現状整理（ローカル実装準拠）
- VLM側は single/multi の推論結果を Webhook 送信可能（`event_dispatcher.py`）。
- payload v1 は `event_type=vlm_inference_result`, `mode`, `text`, `metrics` 等を含む（`docs/development/webhook-events.md`）。
- 外部サービス `services/action-webhook/main.py` は現状「受信ログ出力のみ」。

## 3. 目指す到達点
- 受信サービス側で payload を解釈し、以下を自動判定して実行:
  - Slack通知
  - HTTP機器制御（POST）
  - （将来）LINE/Teams連携、MQTT、ROS2ブリッジ
- 「Yes/No」「キーワード」「危険度スコア」の3系統で判定できるようにする。

## 4. 最速MVP仕様（Phase 1）

### 4.1 受信サービスの最小拡張
`services/action-webhook` に以下を追加:
- `RuleEvaluator`: payload -> action判定
- `RuleEvaluator`: payload -> action判定
- `NotifierSlack`: Slack Incoming Webhookへ送信
- `DeviceClient`: HTTP POST でIP機器制御

### 4.2 ルール（最初に実装する固定仕様）
- Rule-A: Yes/No判定
  - 条件: `text` が `yes` を含む（大文字小文字無視）
  - 動作: Slack通知 + Device POST
  - `no` の場合: Slack通知のみ
- Rule-B: 危険ワード判定
  - 条件: `text` に `ALERT|WARNING|CAUTION` を含む
  - 動作: Slack通知
- Rule-C: 危険度判定
  - 条件: `risk_score >= 0.75`
  - 動作: Slack通知

### 4.3 payload拡張（後方互換維持）
`webhook-events.md` を v1.1 として拡張（既存項目は維持）:
- 追加候補:
  - `risk_score` (number, optional, 0.0-1.0)
  - `labels` (array[string], optional)
  - `camera_id` (string, optional)
  - `stream_id` (string, optional)
  - `inference_prompt_id` (string, optional)
- 互換方針:
  - 未対応受信側は unknown field を無視
  - sender/receiver のどちらか片側更新でも動作継続

### 4.4 推奨プロンプト（risk_scoreを安定抽出）
VLMへの指示は「JSON固定フォーマット」を優先:
```text
あなたは監視アシスタントです。次をJSONのみで返してください。
{"answer":"yes|no|unknown","risk_score":0.0-1.0,"reason":"short"}
```
受信側は以下の順で解釈:
1. JSON parse 成功 -> `answer`, `risk_score` を使用
2. 失敗時 -> 生テキストに対して Rule-A/B を適用

## 5. 実装順（PR分割）

### PR-1: action-webhookのルール実行MVP
- 追加:
  - `services/action-webhook/rules.py`
  - `services/action-webhook/actions/slack.py`
  - `services/action-webhook/actions/device_http.py`
- 変更:
  - `services/action-webhook/main.py`（受信→評価→実行）
- 設定環境変数（受信側）:
  - `ACTION_RULES_ENABLED=1`
  - `SLACK_WEBHOOK_URL`
  - `DEVICE_ENDPOINT_URL`
  - `DEVICE_TIMEOUT_SEC=2`
  - `RISK_THRESHOLD=0.75`
  - 備考: `ACTION_RULES_ENABLED` の実装デフォルトは `0`（無効）。既存挙動への影響を避けるため、明示的に `1` を設定したときのみルール実行する。

### PR-2: payload v1.1拡張（送信側）
- `src/live_vlm_webui/vlm_service.py` or `video_vlm_pipeline.py` で `risk_score` などを詰める
- `docs/development/webhook-events.md` 更新
- `tests/unit` に payload互換テスト追加
- 実装メモ:
  - `inference_prompt_id` は既定で prompt 文字列から `sha256:<16hex>` を生成
  - `LIVE_VLM_INFERENCE_PROMPT_ID` 設定時は上書き
  - `camera_id` / `stream_id` は `LIVE_VLM_CAMERA_ID` / `LIVE_VLM_STREAM_ID` または RTSP/WebRTC の `session_id` から設定

### PR-3: ルール外部化（JSON/YAML）
- 固定if文から設定駆動へ移行
- 例: `services/action-webhook/config/rules.yaml`
- ノーコードでデモシナリオを差し替え可能にする

## 6. デモシナリオ（インパクト重視）
- Demo-1: 侵入検知風
  - Prompt: 「危険行為の有無を yes/no + risk_score で返す」
  - yes または `risk_score>=0.75` で Slack + ライト点灯API
- Demo-2: PPE/安全確認
  - Prompt: 「ヘルメット未着用なら ALERT を含める」
  - `ALERT` 含有で Slack通知
- Demo-3: 夜間監視
  - Prompt: 「異常兆候のみ WARNING を返す」
  - WARNING時のみ通知（通常時は通知抑制）

## 7. 非機能要件
- Webhook/通知失敗は非致命（推論処理を止めない）
- 送信/通知のタイムアウト短め（1-2秒）
- 同一内容の連投抑制（将来）:
  - `dedup_window_sec`（例: 30秒）で同種アラート抑止
- 監査性:
  - `event_id`, `camera_id`, `rule_id`, `action_result` をログ出力

## 8. テスト方針
- Unit:
  - ルール判定（yes/no, keyword, risk閾値）
  - JSON parse成功/失敗時のフォールバック
  - ローカルPython差分対策として `./scripts/run_ci_tests_docker.sh` で Python 3.11 実行経路を用意
- Integration:
  - webhook受信 -> Slack notifier mock -> device client mock
- E2E:
  - live-vlm-webui から action-webhook まで docker compose で疎通

## 9. Physical AI / Embodied AI への拡張設計
- 追加インタフェースを action-webhook 側に切る:
  - `ActionAdapter` 抽象化（Slack, HTTP, MQTT, ROS2）
- 将来拡張例:
  - ROS2 topic publish
  - Jetson上のロボット制御ノード呼び出し
  - デジタルツイン/Cosmos推論結果との統合判定

## 10. 直近2週間の推奨実行計画
- Week 1:
  - PR-1（MVP）完了
  - Slack通知 + 機器POSTの実動デモを作る
- Week 2:
  - PR-2（payload v1.1）
  - risk_score運用開始、閾値チューニング

## 11. 完了定義（MVP）
- yes/noシナリオで分岐動作が確認できる
- ALERT/WARNING/CAUTIONでSlack通知できる
- risk_score閾値でSlack通知できる
- 通知/機器制御失敗時でも live-vlm-webui は継続動作する
- README_MODIFY.md から本ドキュメントへ参照リンクが張られている

## 12. 追加メモ（運用）
- 初期は「誤検知許容・見逃し低減」寄りで閾値を低めに設定
- デモ後に閾値とプロンプトを再調整
- 受信側の秘密情報（Slack URL等）は `.env` 管理、gitコミット禁止
