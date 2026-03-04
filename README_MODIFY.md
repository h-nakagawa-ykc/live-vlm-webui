# README_MODIFY.md

このファイルは、今回実施した「単一画像推論 → 複数フレーム動画解析」拡張のための補足ドキュメントです。
オリジナルの利用手順は `README.md` の **Quick Start** / **Setting Up Your VLM Backend** を参照してください。

---

## ✨ 追加機能（今回の改修）

既存の `frame -> process_frame(pil_img)` フローを、任意で以下に拡張しました。

`frame -> FrameBuffer -> FrameSelector -> Multi-frame VLM inference`

追加コンポーネント:
- `src/live_vlm_webui/frame_buffer.py`
  - 固定長バッファでフレーム蓄積
- `src/live_vlm_webui/frame_selector.py`
  - 等間隔抽出（interval）
  - シーン変化抽出（画像差分しきい値）
- `src/live_vlm_webui/video_vlm_pipeline.py`
  - バッファ管理、代表フレーム選定、複数画像推論、fallback（単画像逐次推論）

変更ファイル:
- `src/live_vlm_webui/video_processor.py`
  - `pipeline` がある場合は `pipeline.process_frame()` を呼ぶ
  - `pipeline` がない場合は従来どおり `vlm_service.process_frame()`
- `src/live_vlm_webui/server.py`
  - `VideoProcessorTrack` 生成時に pipeline を注入（WebRTC/RTSP 両方）

---

## ✅ 既存機能との互換性

- デフォルトは **従来動作のまま**（単一画像推論）です。
- マルチフレームは環境変数で明示的に有効化したときのみ有効になります。
- UI (`static/index.html`) は未変更です。
- OpenAI互換APIが複数画像に未対応でも、**1枚ずつ推論して結果連結**へ自動フォールバックします。

---

## 🚀 Quick Start（改修機能の試し方）

作業ディレクトリ: `live-vlm-webui/`

### 1) 事前確認（構文）

```bash
python -m py_compile \
  src/live_vlm_webui/frame_buffer.py \
  src/live_vlm_webui/frame_selector.py \
  src/live_vlm_webui/video_vlm_pipeline.py \
  src/live_vlm_webui/video_processor.py \
  src/live_vlm_webui/server.py
```

### 2) 従来モード（互換性確認）

```bash
unset LIVE_VLM_ENABLE_MULTI_FRAME
./scripts/start_server.sh
```

- 期待結果: 従来の単一画像推論で動作する

### 3) マルチフレームモード（新機能確認）

```bash
export LIVE_VLM_ENABLE_MULTI_FRAME=1
export LIVE_VLM_BUFFER_SIZE=16
export LIVE_VLM_TRIGGER_SIZE=4
export LIVE_VLM_TARGET_FRAMES=4
export LIVE_VLM_INTERVAL_STEP=1
export LIVE_VLM_SCENE_THRESHOLD=20.0

./scripts/start_server.sh
```

- 期待結果:
  - フレーム蓄積後に複数画像推論を実施
  - 非対応APIでは fallback が動作

---

## ⚙️ 追加環境変数（意味と挙動）

### A. マルチフレーム推論関連

- `LIVE_VLM_ENABLE_MULTI_FRAME`
  - 意味: マルチフレーム推論の有効/無効
  - 値: `1/true/yes/on` で有効（それ以外は無効）
  - 変化: `0` のとき従来の単一画像推論のみ動作

- `LIVE_VLM_BUFFER_SIZE`
  - 意味: バッファに保持する最大フレーム数
  - 変化: 大きいほど多くのフレームを保持できるが、メモリ使用量は増える

- `LIVE_VLM_TRIGGER_SIZE`
  - 意味: 推論を開始する最小蓄積フレーム数
  - 変化: 大きいほど応答頻度は下がり、文脈は増えやすい

- `LIVE_VLM_TARGET_FRAMES`
  - 意味: 最終的にVLMへ送る代表フレーム数上限
  - 変化: 大きいほど情報量は増えるが、推論負荷と遅延が増える

- `LIVE_VLM_INTERVAL_STEP`
  - 意味: 代表フレーム抽出時の等間隔ステップ
  - 変化: 値を上げるほど間引きが強くなり、近接フレームが減る

- `LIVE_VLM_SCENE_THRESHOLD`
  - 意味: シーン変化判定しきい値（平均絶対画素差）
  - 変化: 値が低いほど変化判定が増え、値が高いほど減る

### B. Webhook連携関連

- `LIVE_VLM_WEBHOOK_ENABLED`
  - 意味: Webhook送信機能の有効/無効
  - 値: `1/true/yes/on` で有効（デフォルト無効）
  - 変化: 無効時はWebhook送信処理を完全にスキップ

- `LIVE_VLM_WEBHOOK_URL`
  - 意味: 送信先エンドポイント（例: `http://localhost:8081/events`）
  - 変化: 未設定時は `ENABLED=1` でも安全側で送信無効

- `LIVE_VLM_WEBHOOK_TIMEOUT_SEC`
  - 意味: 送信タイムアウト秒
  - 変化: 小さいほど早く失敗復帰、大きいほど送信待ちが長くなる

- `LIVE_VLM_WEBHOOK_MODE`
  - 意味: 送信対象モード
  - 値: `single` / `multi` / `both`
  - 変化:
    - `single`: 単一画像推論結果のみ送信
    - `multi`: マルチフレーム推論結果のみ送信
    - `both`: 両方送信

- `LIVE_VLM_WEBHOOK_SAMPLE_EVERY`
  - 意味: N件に1回送信するサンプリング間隔
  - 変化: 値を上げると送信頻度が下がり、受信側負荷を抑制

- `LIVE_VLM_WEBHOOK_INCLUDE_METRICS`
  - 意味: payloadにメトリクスを含めるか
  - 値: `1` で含む / `0` で含まない
  - 変化: 有効時は `latency` などを受信側で利用可能

### C. 設定変更時の注意

- 環境変数はサーバ起動時に読み込まれるため、値変更後は再起動が必要
- 不正値は安全なデフォルトにフォールバック（例: timeout/sample）
- Webhook送信失敗時でもVLM推論とWebUI更新は継続（非機能要件）

---

## 🔎 動作確認チェックリスト

1. サーバ起動後に WebUI (`https://localhost:8090`) へアクセスできる
2. 従来モードで推論結果が従来どおり更新される
3. マルチフレームモードでログに以下が出る
   - 成功: `Multi-frame VLM response generated ...`
   - fallback: `Multi-image inference failed, using single-image fallback ...`
4. RTSP パスでもエラーなく `VideoProcessorTrack` が作成される

---

## 🧭 トラブル時の切り戻し

```bash
unset LIVE_VLM_ENABLE_MULTI_FRAME
./scripts/start_server.sh
```

これで常に従来の単一画像推論パスを使用します。

---

## 🧪 Webhook受信サンプル（Issue 6）

ローカルデモ用に `action-webhook` サービスを追加しました。  
`POST /events` で受信した payload をログ出力します。

### 起動

```bash
docker compose -f docker/docker-compose.yml up -d action-webhook
docker compose -f docker/docker-compose.yml logs -f action-webhook
```

### live-vlm-webui から送信する設定例

```bash
export LIVE_VLM_WEBHOOK_ENABLED=1
export LIVE_VLM_WEBHOOK_URL=http://localhost:8081/events
export LIVE_VLM_WEBHOOK_TIMEOUT_SEC=2
```

### 確認ポイント

1. WebUIで推論を実行すると `action-webhook` 側に `POST /events` の受信ログが出る  
2. 送信先を不正URLにしても、VLM推論とWebUI更新が継続する

---

## ✅ Issue 7 テスト実行手順（Docker）

ホスト環境のPython差分を避けるため、以下のDockerコマンドで unit test を実行できます。

```bash
docker run --rm -it \
  -v "$PWD":/work \
  -w /work \
  python:3.11-slim-bullseye \
  bash -lc "
    apt-get update &&
    apt-get install -y --no-install-recommends \
      libglib2.0-0 libsm6 libxext6 libxrender1 libxcb1 libgl1 &&
    rm -rf /var/lib/apt/lists/* &&
    python -m pip install -U pip &&
    pip install -e '.[dev]' &&
    python -m pytest tests/unit/test_event_dispatcher.py tests/unit/test_vlm_service_webhook_resilience.py -v
  "
```

期待結果:
- `tests/unit/test_event_dispatcher.py` が PASS
- `tests/unit/test_vlm_service_webhook_resilience.py` が PASS
- `2 passed` と表示される

---

## 📘 Issue 8 運用手順（Webhook有効化/無効化/切り戻し）

このセクションは、Webhook連携を安全に運用するための手順です。

### 1) Webhook有効化（ローカル実行）

```bash
export LIVE_VLM_WEBHOOK_ENABLED=1
export LIVE_VLM_WEBHOOK_URL=http://localhost:8081/events
export LIVE_VLM_WEBHOOK_TIMEOUT_SEC=2
export LIVE_VLM_WEBHOOK_MODE=both
export LIVE_VLM_WEBHOOK_SAMPLE_EVERY=1
export LIVE_VLM_WEBHOOK_INCLUDE_METRICS=1

./scripts/start_server.sh
```

### 2) Webhook無効化（既存挙動に戻す）

```bash
unset LIVE_VLM_WEBHOOK_ENABLED
unset LIVE_VLM_WEBHOOK_URL
unset LIVE_VLM_WEBHOOK_TIMEOUT_SEC
unset LIVE_VLM_WEBHOOK_MODE
unset LIVE_VLM_WEBHOOK_SAMPLE_EVERY
unset LIVE_VLM_WEBHOOK_INCLUDE_METRICS

./scripts/start_server.sh
```

### 3) 送信失敗時の切り戻し（最短）

1. Webhook設定を無効化（上記 `unset` を実行）  
2. `start_server.sh` を再起動  
3. WebUIで推論が継続することを確認

### 4) Docker Composeでの確認手順

```bash
# 受信側を起動
docker compose -f docker/docker-compose.yml up -d action-webhook

# 受信ログ確認
docker compose -f docker/docker-compose.yml logs -f action-webhook
```

別ターミナルで live-vlm-webui を起動し、推論を実行する。  
`action-webhook` ログに `POST /events` が出力されれば連携成功。

### 5) 障害時確認（非機能要件）

- `LIVE_VLM_WEBHOOK_URL` を到達不能URLに変更して起動
- 期待結果:
  - Webhook送信エラーはログに出る
  - VLM推論結果のWebUI表示は継続する

### 6) 代表的なトラブルシュート

- 症状: `POST /events` が出ない  
  - 確認: `LIVE_VLM_WEBHOOK_ENABLED=1` か  
  - 確認: `LIVE_VLM_WEBHOOK_URL` が正しいか

- 症状: 受信側が起動しない  
  - 確認: `docker compose ... logs action-webhook`  
  - 確認: ポート `8081` の競合有無

- 症状: 送信エラーが継続  
  - 対応: 一時的にWebhookを無効化し、推論機能を優先
