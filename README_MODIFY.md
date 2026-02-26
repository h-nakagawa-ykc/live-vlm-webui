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

## ⚙️ 追加環境変数

- `LIVE_VLM_ENABLE_MULTI_FRAME`
  - `1/true/yes/on` で有効、それ以外は無効（デフォルト無効）
- `LIVE_VLM_BUFFER_SIZE`
  - バッファ最大保持数（例: `16`）
- `LIVE_VLM_TRIGGER_SIZE`
  - 推論起動に必要な最小フレーム数（例: `4`）
- `LIVE_VLM_TARGET_FRAMES`
  - 推論に使う代表フレーム上限（例: `4`）
- `LIVE_VLM_INTERVAL_STEP`
  - 等間隔抽出のステップ幅（例: `1`, `2`, `3`）
- `LIVE_VLM_SCENE_THRESHOLD`
  - シーン変化判定しきい値（平均差分、例: `20.0`）

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
