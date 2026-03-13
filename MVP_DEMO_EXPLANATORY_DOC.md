# live-vlm-webui 改修版: MVPデモ説明資料（Webhook連携）

## 1. この資料の目的
この資料は、`live-vlm-webui` フォーク改修版における以下を、**現状ソースコード準拠**で説明するためのものです。
- 何を追加したか（マルチフレーム推論 + Webhook連携）
- MVPデモで何を見せるか（VLM結果を外部アクションに接続）
- 現在の実装状態と、今後の拡張ロードマップ

対象リポジトリ: `./live-vlm-webui`

---

## 2. 全体像（実装済み）

### 2.1 追加済みの主要機能
- マルチフレーム推論パイプライン
  - `src/live_vlm_webui/frame_buffer.py`
  - `src/live_vlm_webui/frame_selector.py`
  - `src/live_vlm_webui/video_vlm_pipeline.py`
- Webhook送信機能（VLM推論結果の非同期通知）
  - `src/live_vlm_webui/event_dispatcher.py`
  - `src/live_vlm_webui/webhook_config.py`
  - `src/live_vlm_webui/vlm_service.py`
- Webhook受信サーバー（action-webhook）
  - `services/action-webhook/main.py`
  - `services/action-webhook/rules.py`
  - `services/action-webhook/actions/slack.py`
  - `services/action-webhook/actions/device_http.py`
  - `services/action-webhook/rule_configs/rules.yaml`

### 2.2 動作モード
- 単一フレーム推論（従来互換）
- マルチフレーム推論（環境変数で有効化時のみ）
- Webhook送信（環境変数で有効化時のみ）

---

## 3. システム構成（MVPデモ想定）

### 3.1 データフロー
1. カメラ入力（WebRTC または RTSP）
2. `VideoProcessorTrack` がフレームを間引いて推論経路へ投入
3. 推論経路
   - Single: `VLMService.process_frame()`
   - Multi: `VideoVLMPipeline.process_frame()`
4. 推論結果を WebUI へ反映（WebSocket）
5. 同時に Webhook payload を `POST /events` 送信
6. `action-webhook` がルール評価
7. 条件一致で Slack通知 / HTTP機器制御 を実行

### 3.2 コンテナ構成（docker-compose）
`docker/docker-compose.override.yml` では、以下連携を前提に構成済み。
- `live-vlm-webui`（送信側）
- `action-webhook`（受信側、`8081`）
- `ollama` / `nim` などVLMバックエンド（profile選択）

---

## 4. 送信payload仕様（v1.1）
参照: `docs/development/webhook-events.md`

### 4.1 主要フィールド
- 必須: `event_id`, `event_type`, `timestamp_unix`, `mode`, `text`, `model`, `api_base`
- 任意:
  - `metrics`
  - `risk_score`, `labels`
  - `camera_id`, `stream_id`, `inference_prompt_id`
  - （multi時）`selected_frame_count`, `buffered_frame_count`, `used_fallback`

### 4.2 後方互換方針
- unknown field は受信側で無視
- v1.xで既存項目の意味は維持

---

## 5. action-webhook の判定・実行ロジック

### 5.1 受信API
- `GET /healthz`
- `POST /events`

### 5.2 ルール評価（`RuleEvaluator`）
現在のデフォルトルール:
- `rule_yes`: answer=yes -> `slack + device`
- `rule_no`: answer=no -> `slack`
- `rule_keyword_alert`: textに `ALERT|WARNING|CAUTION` -> `slack`
- `rule_risk_high`: `risk_score >= threshold` -> `slack`

### 5.3 実行アクション
- Slack Incoming Webhook送信
- HTTP POST による機器連携
- 失敗しても `/events` 自体は受理継続（非致命設計）

---

## 6. MVPデモで見せる内容（推奨）

### 6.1 デモ観点
- 観点A: 推論結果のリアルタイム可視化（WebUI）
- 観点B: 推論結果の外部通知（Webhook -> Slack）
- 観点C: 推論結果の外部制御（Webhook -> Device HTTP）

### 6.2 推奨シナリオ
1. Yes/No判定
- `yes` で Slack + Device
- `no` で Slackのみ

2. 危険キーワード判定
- `ALERT` / `WARNING` / `CAUTION` を含む応答で通知

3. risk_score判定
- `risk_score >= RISK_THRESHOLD` で通知

---

## 7. 実行設定（環境変数）

### 7.1 送信側（live-vlm-webui）
- `LIVE_VLM_ENABLE_MULTI_FRAME`
- `LIVE_VLM_WEBHOOK_ENABLED`
- `LIVE_VLM_WEBHOOK_URL`
- `LIVE_VLM_WEBHOOK_MODE`
- `LIVE_VLM_WEBHOOK_SAMPLE_EVERY`
- `LIVE_VLM_WEBHOOK_INCLUDE_METRICS`
- `LIVE_VLM_CAMERA_ID`, `LIVE_VLM_STREAM_ID`, `LIVE_VLM_INFERENCE_PROMPT_ID`

### 7.2 受信側（action-webhook）
- `ACTION_RULES_ENABLED`
- `ACTION_RULES_FILE`
- `RISK_THRESHOLD`
- `SLACK_WEBHOOK_URL`
- `DEVICE_ENDPOINT_URL`
- `DEVICE_TIMEOUT_SEC`

---

## 8. Dockerテスト結果（2026-03-12 実行）
実行スクリプト:
- `scripts/run_ci_tests_docker.sh`

実行対象:
- `tests/unit/test_event_dispatcher.py`
- `tests/unit/test_vlm_service_webhook_resilience.py`
- `tests/unit/test_action_webhook_rules.py`
- `tests/unit/test_webhook_payload_v11.py`
- `tests/integration/test_action_webhook_integration.py`

結果サマリ:
- 9 passed
- 2 failed
- 3 skipped

失敗テスト:
- `test_risk_rule_triggers_slack_with_payload_field`
- `test_multiple_rule_matches_dedupe_actions`

示唆:
- `services/action-webhook/rules.py` の `risk_score` 抽出実装と、テスト期待（payload直値 `risk_score` の評価）に不整合がある可能性

スキップ:
- integration 3件は、`fastapi` モジュール解決条件により skip

---

## 9. 現状評価（MVP観点）

### 9.1 できていること
- WebUIの推論処理を壊さず、Webhook送信を非同期で追加
- 単一/複数フレームの両経路からpayload送信
- 受信側でルール評価し、通知/外部POSTまで到達可能な骨格実装
- ルール外部化（YAML）への移行方針が既に実装に反映

### 9.2 残課題（デモ前に詰めるべき点）
- `risk_score` 判定の実装・テスト整合性修正
- integration test の実行前提（fastapi）をDocker環境で安定化
- 実Slack/実機器エンドポイントへの手動疎通確認（最終スモーク）

---

## 10. ロードマップ位置づけ
参照: `docs/development/action-orchestration-roadmap-ja.md`

- Phase 1（MVP）
  - 受信 -> 判定 -> Slack/Device 実行まで
- Phase 2
  - payload v1.1運用の安定化（risk_score活用）
- Phase 3
  - ルール高度化（外部定義、複合条件、抑制/監査）
- 将来
  - MQTT / ROS2 / Physical AI 連携

---

## 11. 関連ドキュメント
- `README_MODIFY.md`
- `docs/development/webhook-events.md`
- `docs/development/action-orchestration-roadmap-ja.md`
- `docs/development/action-webhook-manual-test-ja.md`
- `docs/development/action-webhook-integration-test-cases-ja.md`
- `services/action-webhook/README.md`

