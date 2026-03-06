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

### D. 詳細挙動ガイド（FAQ）

#### D-1. マルチフレーム推論モードの実際の流れ

`LIVE_VLM_ENABLE_MULTI_FRAME=1` の場合のみ `VideoVLMPipeline` が生成されます。  
`0`（または未設定）の場合は従来どおり単一フレーム推論です。

実処理は次の順序です:
1. `VideoProcessorTrack.recv()` が `process_every_n_frames` 到達時のみ `pipeline.process_frame()` を呼ぶ
2. pipeline がフレームを `FrameBuffer` に追加
3. バッファサイズが `LIVE_VLM_TRIGGER_SIZE` 未満なら推論しない
4. `TRIGGER_SIZE` 到達時に `snapshot()` して **直後に `clear()`**
5. 取得したフレーム群から代表抽出:
   - 等間隔抽出（`LIVE_VLM_INTERVAL_STEP`）
   - シーン変化抽出（`LIVE_VLM_SCENE_THRESHOLD`）
6. `LIVE_VLM_TARGET_FRAMES` 上限で代表フレームを選んで推論
7. 複数画像推論失敗時は1枚ずつの fallback 推論

> 注意: 「N番目と N-step 番目を逐次比較する」実装ではありません。  
> 実装は、`snapshot` したフレーム配列に対するバッチ選択です。

代表抽出の実装詳細:
- `interval` 抽出と `scene-change` 抽出は**独立に実行**し、最後にマージ（重複除去）します。
- `interval` は `frames[::step]` で抽出し、末尾フレームが漏れた場合は末尾を追加します。
- `scene-change` は「先頭フレームをまず採用」し、その後は**直近で採用したフレーム**との差分を見ます（単純な隣接比較でも、常に先頭基準でもありません）。
- 最終的に `LIVE_VLM_TARGET_FRAMES` 上限で切り詰めます。

`TRIGGER_SIZE=5` の例:
- `INTERVAL_STEP=1`: interval候補は 5枚
- `INTERVAL_STEP=2`: interval候補は 1,3,5番目
- `INTERVAL_STEP=3`: interval候補は 1,4,5番目（末尾補完が入る）
- `INTERVAL_STEP=4`: interval候補は 1,5番目
- `INTERVAL_STEP>5`: interval候補は 1番目のみ（末尾補完で5番目も入る場合あり）

`SCENE_THRESHOLD` の補足:
- 画素差分の平均値（0〜255スケール）で判定します。0〜100に限定されません。
- しきい値が低いほど採用されやすく、高いほど採用されにくくなります。
- フレーム群が空でなければ、scene抽出側は最低1枚（先頭）を返します。
- 代表0枚は通常発生しません（`TARGET_FRAMES<=0` など不正設定は除く）。

推論へ実際に送信されるフレーム数:
- マルチフレーム推論時の送信枚数は固定値ではなく、代表抽出結果に応じて変動します。
- 正常設定（`TARGET_FRAMES>0`）かつ `TRIGGER_SIZE` 到達済みであれば、通常0枚にはなりません。
- 実際の送信枚数は概ね `1 〜 min(TARGET_FRAMES, 抽出結果枚数)` の範囲になります。

#### D-2. バッファの方式（```LIVE_VLM_BUFFER_SIZE```）

- `FrameBuffer` は `deque(maxlen=BUFFER_SIZE)` を使うため **キュー方式** です。
- 上限超過時は最古フレームが自動的に捨てられます。
- ただし通常フローでは `TRIGGER_SIZE` 到達時に `clear()` されるため、毎回空に戻ります。
- `BUFFER_SIZE=TRIGGER_SIZE` は問題ありません。
- `BUFFER_SIZE<TRIGGER_SIZE` は実質ミスコンフィグで、到達不能のため推論が起きません（例外ではなく、待機し続ける挙動）。

#### D-3. `TRIGGER_SIZE` と `TARGET_FRAMES` の関係

- `TRIGGER_SIZE`: 「何枚たまったら推論開始するか」
- `TARGET_FRAMES`: 「推論に何枚まで渡すか」

例:
- `TRIGGER_SIZE=4`, `TARGET_FRAMES=3`
  - 4枚たまったら推論開始
  - 代表抽出で最大3枚をVLMへ送信
- `TRIGGER_SIZE=4`, `TARGET_FRAMES=5`
  - 4枚たまったら推論開始
  - 送信枚数は最大4枚（存在しない5枚目は送れない）
  - 例外にはならない

#### D-4. 処理後のバッファ

- 推論実行前に `snapshot + clear` されるため、使用したフレームはバッファから除去されます。

#### D-5. シングルフレーム推論モード

- `LIVE_VLM_ENABLE_MULTI_FRAME=0` のとき、追加した動画パイプラインは使用されません。
- 従来どおり `vlm_service.process_frame()` が呼ばれます。
- マルチフレーム関連の環境変数は、pipeline未生成のため実行時には効きません。

#### D-6. Webhook環境変数の挙動

- `LIVE_VLM_WEBHOOK_TIMEOUT_SEC`
  - 単位は秒です（ミリ秒ではない）。
  - HTTPリクエスト全体のタイムアウトとして扱われます。

- `LIVE_VLM_WEBHOOK_MODE`
  - `both`: single/multi 両イベントを送信対象
  - `single`: singleイベントのみ送信（multiイベントは送らない）
  - `multi`: multiイベントのみ送信（singleイベントは送らない）

`LIVE_VLM_ENABLE_MULTI_FRAME` との組み合わせ:
- `WEBHOOK_MODE=single` かつ `ENABLE_MULTI_FRAME=1`
  - 実行される推論は multi 経路なので、送信対象モード不一致で基本送信されない
- `WEBHOOK_MODE=multi` かつ `ENABLE_MULTI_FRAME=0`
  - single 経路しか実行されないため、基本送信されない
- `WEBHOOK_MODE=both`
  - 実行された推論モードに応じて送信される

- `LIVE_VLM_WEBHOOK_SAMPLE_EVERY`
  - 「対象モードのイベントを N件に1回送信」の意味です。
  - `1`: 毎回送信
  - `3`: 1,2件目はスキップ、3件目送信（以降 6,9...）
  - カウントは `WEBHOOK_MODE` に一致したイベントだけが対象です（single/multi混在時に mode 絞り込み後でカウント）。

#### D-7. デフォルト値（未設定時）

- マルチフレーム:
  - `LIVE_VLM_ENABLE_MULTI_FRAME=0`（無効）
  - `BUFFER_SIZE=16`
  - `TRIGGER_SIZE=4`
  - `TARGET_FRAMES=4`
  - `INTERVAL_STEP=1`
  - `SCENE_THRESHOLD=20.0`

- Webhook:
  - `LIVE_VLM_WEBHOOK_ENABLED=0`（無効）
  - `LIVE_VLM_WEBHOOK_URL=""`
  - `LIVE_VLM_WEBHOOK_TIMEOUT_SEC=2.0`
  - `LIVE_VLM_WEBHOOK_MODE=both`
  - `LIVE_VLM_WEBHOOK_SAMPLE_EVERY=1`
  - `LIVE_VLM_WEBHOOK_INCLUDE_METRICS=1`

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

---

## 🗺️ 今後の開発方針（MVP〜拡張）

- 追加機能の実装計画・PR分割・デモシナリオは以下を参照:
  - `docs/development/action-orchestration-roadmap-ja.md`
