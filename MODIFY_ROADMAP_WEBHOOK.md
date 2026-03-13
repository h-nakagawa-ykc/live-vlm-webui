# MODIFY_ROADMAP_WEBHOOK.md

## 目的
この文書は、以下2点を将来参照しやすい形で残すための記録です。
1. 先の回答「1. 誰が推論をトリガーするか」〜「8. 外部連携方針」の要点。
2. プロトタイプ最優先での「Webhook POST連携」実装案（現リポジトリ構造を前提）。

---

## 1) 現在実装のデータフロー要点（1〜8の要約）

### 1. 推論トリガー主体
- 推論トリガーはフロントエンドではなくバックエンド側。
- `VideoProcessorTrack.recv()` がフレーム受信ループ内で、`process_every_n_frames` 到達時に推論投入を行う。

### 2. 従来モードとマルチフレームモードの分岐
- 分岐点は `video_processor.py` の以下処理。
- `pipeline` があれば `pipeline.process_frame(pil_img)`。
- なければ従来どおり `vlm_service.process_frame(pil_img)`。

### 3. レスポンス配信の仕組み
- `recv()` のたびに `vlm_service.get_current_response()` と `get_metrics()` を読む。
- `text_callback` によりサーバ側がWebSocketへ push 配信する。
- フロントは pull ではなく、`/ws` 常時接続でイベント受信する。

### 4. フロントの受信と描画
- フロントは `new WebSocket(.../ws)` で接続。
- `type === "vlm_response"` を受信したらテキスト・メトリクスを描画。
- 現在の payload は主に `text` と `metrics`。入力フレームIDやタイムスタンプは含まれない。

### 5. マルチフレーム時の内部流れ
- フレームをバッファへ追加。
- `LIVE_VLM_TRIGGER_SIZE` 到達で snapshot + clear。
- 代表抽出（interval + scene-change）後、複数画像推論を試行。
- 非対応時は1枚ずつ推論して連結（fallback）。

### 6. 環境変数の実質的意味
- `LIVE_VLM_TRIGGER_SIZE`: 推論を起動する最小蓄積枚数。
- `LIVE_VLM_BUFFER_SIZE`: バッファ上限。
- `LIVE_VLM_TARGET_FRAMES`: VLMに渡す代表フレーム数上限。
- `LIVE_VLM_INTERVAL_STEP`: 抽出時の等間隔ステップ。
- `LIVE_VLM_SCENE_THRESHOLD`: 平均絶対画素差分のしきい値。

### 7. 既知ギャップ
- 解析結果と入力フレームの厳密対応（frame_id / capture_ts）がUIに出ない。
- 「この結果がどの瞬間の映像か」を厳密に示せない。

### 8. 次方針
- プロトタイプ最優先なら、推論完了イベントを外部へ送るWebhook連携が最短。

---

## 2) Webhook POST連携の実装方針（最短経路）

## 方針
- 最小差分で `live-vlm-webui` に「送信アダプタ」を追加し、推論完了時に外部HTTPへPOSTする。
- 受信先は別サービス（FastAPIなど）としてDocker Composeで同時起動可能にする。

## ディレクトリ見直し案

### 推奨（段階1: 最小差分）
- 既存モノリス内に送信モジュールを追加。
- 追加先候補:
  - `src/live_vlm_webui/event_dispatcher.py`
  - `src/live_vlm_webui/event_models.py`（任意）
- 理由:
  - 既存 `VLMService` / `VideoVLMPipeline` から呼び出しやすい。
  - UIやWebRTC構成を崩さず、短期間で動く。

### 次段階（段階2: マイクロサービス志向）
- 受信・判定・通知を別コンテナへ分離。
- 例:
  - `services/action-webhook/`（FastAPI）
    - `main.py` (`POST /events`)
    - `rules.py`（yes/no判定）
    - `notifier.py`（Slack/Email/Push）
- `docker/docker-compose.yml` へ `action-webhook` サービスを追加。

## 最短実装のI/O仕様（提案）

### 送信トリガー
- 推論結果確定直後（単一/マルチ共通）で送信。

### POST先
- 環境変数で指定。
- 例: `LIVE_VLM_WEBHOOK_URL=http://action-webhook:8081/events`

### payload例
```json
{
  "event_type": "vlm_inference_result",
  "text": "...",
  "model": "...",
  "api_base": "...",
  "latency_ms": 123,
  "avg_latency_ms": 150,
  "total_inferences": 42,
  "is_processing": false,
  "mode": "single|multi",
  "timestamp": "2026-02-19T12:34:56Z"
}
```

## 実装ステップ（プロトタイプ優先）
1. `event_dispatcher.py` を追加（非同期HTTP POST、タイムアウト、例外ログ）。
2. `VLMService.process_frame()` と `VideoVLMPipeline.process_frame()` の完了点で dispatch 呼び出し。
3. 環境変数追加:
   - `LIVE_VLM_WEBHOOK_ENABLED=1`
   - `LIVE_VLM_WEBHOOK_URL=...`
   - `LIVE_VLM_WEBHOOK_TIMEOUT_SEC=2.0`
4. composeに受信サンプルサービスを追加（FastAPI）。
5. yes/no判定ルールを受信側で実装し、通知処理に接続。

## 非機能要件（最低限）
- 送信失敗でメイン処理を止めない（fire-and-forget + 例外握りつぶしではなくログ化）。
- タイムアウト短め（リアルタイム性重視）。
- リトライは段階2で追加（まずは単純実装）。

## 将来拡張
- frame_id / capture_ts / source_id を payload へ追加し、追跡可能性を改善。
- Webhookに加えてMQ（Redis Streams, NATS, Kafka）へ拡張。
- ルールエンジン化（しきい値、キーワード、状態遷移）。

---

## 結論
- まずはモノリス内にWebhook送信アダプタを追加する構成が、最短かつ低リスク。
- その後、受信・判定・通知を `services/` に切り出す二段階移行が、プロトタイピングから本番志向への移行に最も適している。

---

## 3) 互換性維持ポリシー（既存リアルタイムVLMを壊さない）

### 基本方針
- Webhook連携は **デフォルト無効** とし、既存挙動を変更しない。
- 有効化は環境変数で明示的に行う。
- 送信失敗時もVLM推論フローは継続し、WebUI更新にも影響させない。

### 追加する環境変数（提案）
- `LIVE_VLM_WEBHOOK_ENABLED`
  - `1/true/yes/on` のときのみ送信有効（デフォルト `0`）。
- `LIVE_VLM_WEBHOOK_URL`
  - 送信先URL（未設定時は送信しない）。
- `LIVE_VLM_WEBHOOK_TIMEOUT_SEC`
  - 送信タイムアウト秒（例: `2.0`）。
- `LIVE_VLM_WEBHOOK_MODE`
  - `single|multi|both`（どの推論モード結果を送信するか）。
- `LIVE_VLM_WEBHOOK_SAMPLE_EVERY`
  - `N`件に1回送信（デフォルト `1`）。
- `LIVE_VLM_WEBHOOK_INCLUDE_METRICS`
  - メトリクス同梱のON/OFF（デフォルト `1`）。

### 互換性の受け入れ条件
- 上記環境変数を一切設定しない場合、現行動作と同一であること。
- Webhook送信先停止時でも、`vlm_response` のWebSocket配信が継続すること。
- 単一推論/マルチ推論の切替ロジックに副作用を持ち込まないこと。

---

## 4) 実装タスク一覧（Issue化しやすい粒度）

以下は、GitHub Issueとしてそのまま登録できる粒度を意識した分解。

### Issue 1: Webhook設定の導入（環境変数と設定解決）
- 目的: Webhookの有効/無効を完全に設定で制御可能にする。
- 変更対象:
  - `src/live_vlm_webui/server.py`（起動時設定ロード）
  - `src/live_vlm_webui/__init__.py` or 新規 `config_webhook.py`（任意）
- 実装項目:
  - `LIVE_VLM_WEBHOOK_ENABLED` 等の読み取り。
  - 未設定・不正値時の安全なデフォルト。
- 完了条件:
  - デフォルト無効で既存挙動が変化しない。
  - 設定値がログで確認できる（機密情報はマスク）。

### Issue 2: Event Dispatcher追加（非同期POST）
- 目的: 推論結果イベントを外部へ送信する共通部品を追加。
- 変更対象:
  - 新規 `src/live_vlm_webui/event_dispatcher.py`
- 実装項目:
  - 非同期POST（aiohttp/httpxどちらか）。
  - タイムアウト・HTTPエラー・接続エラーのログ化。
  - 例外を上位へ伝播させず、呼び出し元処理を継続。
- 完了条件:
  - 送信失敗でも例外でメインループが停止しない。
  - 成功/失敗ログに event_id を含め追跡できる。

### Issue 3: 単一推論完了時のイベント送信フック
- 目的: 従来モードの推論結果をWebhook送信できるようにする。
- 変更対象:
  - `src/live_vlm_webui/vlm_service.py`
- 実装項目:
  - `process_frame()` 完了時に dispatcher 呼び出し。
  - payloadに `mode=single` を付与。
  - `LIVE_VLM_WEBHOOK_MODE` が `single|both` の時のみ送信。
- 完了条件:
  - 従来推論の結果表示は従来どおり。
  - Webhook有効時のみ送信される。

### Issue 4: マルチ推論完了時のイベント送信フック
- 目的: マルチフレーム推論結果も同一仕組みで送信する。
- 変更対象:
  - `src/live_vlm_webui/video_vlm_pipeline.py`
- 実装項目:
  - 推論確定点（multi/fallbackの最終結果）で dispatcher 呼び出し。
  - payloadに `mode=multi` と代表フレーム数を付与。
  - `LIVE_VLM_WEBHOOK_MODE` が `multi|both` の時のみ送信。
- 完了条件:
  - マルチ推論機能を壊さずに送信可能。
  - fallback時も同様に送信される。

### Issue 5: Payload仕様の固定化（v1）
- 目的: 連携先が扱いやすい安定フォーマットを定義。
- 変更対象:
  - `CODEX_ANSWER.md` もしくは新規 `docs/development/webhook-events.md`
- 実装項目:
  - 必須/任意フィールド定義。
  - 例: `event_type`, `timestamp`, `mode`, `text`, `metrics`, `source`。
  - 互換性ポリシー（後方互換・フィールド追加方針）。
- 完了条件:
  - ドキュメントを見れば受信側実装が可能。

### Issue 6: Docker Composeに受信サンプルサービス追加（任意だが推奨）
- 目的: デモで即確認できる受信先を同梱。
- 変更対象:
  - `docker/docker-compose.yml`
  - 新規 `services/action-webhook/`（FastAPI最小実装）
- 実装項目:
  - `POST /events` を受けてログ出力。
  - `live-vlm-webui` からの送信先を service名で解決。
- 完了条件:
  - `docker compose` 起動で送受信を確認できる。

### Issue 7: 非機能テスト（障害時継続性）
- 目的: 送信障害がVLM本体へ影響しないことを保証。
- 変更対象:
  - `tests/unit/` へ dispatcher テスト追加
  - `tests/integration/` へ送信失敗シナリオ追加
- 実装項目:
  - タイムアウト・5xx・接続拒否のケース。
  - 失敗後も `vlm_response` 配信継続を確認。
- 完了条件:
  - テストで「非停止」が再現性を持って確認できる。

### Issue 8: README_MODIFY.md / 運用手順更新
- 目的: 利用者が有効化・切り戻しを迷わない状態にする。
- 変更対象:
  - `README_MODIFY.md`
  - 必要なら `README.md` からリンク
- 実装項目:
  - Webhook有効化手順、無効化手順、確認コマンド。
  - 障害時の切り戻し（環境変数解除 + 再起動）。
- 完了条件:
  - ドキュメントのみで実行/確認できる。

---

## 5) 推奨実装順（最短で価値を出す順）
1. Issue 1（設定）
2. Issue 2（dispatcher）
3. Issue 3（single連携）
4. Issue 4（multi連携）
5. Issue 7（非機能テスト）
6. Issue 8（ドキュメント）
7. Issue 6（受信サービス同梱）
8. Issue 5（payload仕様固定化を最終レビュー）
