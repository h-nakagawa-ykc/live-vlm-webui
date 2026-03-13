# GITHUB_ISSUE_TEMPLATES_MODIFY_ROADMAP_WEBHOOK.md

このドキュメントは、`CODEX_ANSWER.md` の Issue 1〜8 を GitHub Issue にそのまま転記できる形式（Title/Body/AC/DoD）にしたテンプレート集です。

---

## Issue 1
### Title
`feat: add webhook configuration loading with backward-compatible defaults`

### Body
#### Background
Webhook連携を導入するが、既存のリアルタイムVLM挙動は壊さない。

#### Goal
環境変数でWebhook機能を有効/無効制御できる設定解決レイヤーを追加する。

#### Scope
- `LIVE_VLM_WEBHOOK_ENABLED`
- `LIVE_VLM_WEBHOOK_URL`
- `LIVE_VLM_WEBHOOK_TIMEOUT_SEC`
- `LIVE_VLM_WEBHOOK_MODE`
- `LIVE_VLM_WEBHOOK_SAMPLE_EVERY`
- `LIVE_VLM_WEBHOOK_INCLUDE_METRICS`

#### Out of Scope
- 実際のHTTP POST送信実装
- 受信側サービス実装

### AC (Acceptance Criteria)
- 環境変数未設定時はWebhook無効になる。
- 既存挙動（単一/マルチ推論、WebSocket配信）に変化がない。
- 不正値を安全なデフォルトへフォールバックできる。
- 起動ログで有効設定が確認できる（機密情報はマスク）。

### DoD (Definition of Done)
- 設定解決コードが追加され、単体テストまたは手動確認記録がある。
- README_MODIFYまたは関連ドキュメントに設定項目が追記される。

---

## Issue 2
### Title
`feat: implement async webhook event dispatcher with non-blocking failure handling`

### Body
#### Background
VLM推論結果を外部サービスへ送るため、共通の送信アダプタが必要。

#### Goal
非同期POSTを行う `event_dispatcher` を追加し、失敗時もメイン処理を止めない。

#### Scope
- 新規 `src/live_vlm_webui/event_dispatcher.py`
- タイムアウト、HTTPエラー、接続エラー時のログ化
- 呼び出し元へ致命例外を伝播させない

#### Out of Scope
- `vlm_service` / `video_vlm_pipeline` への呼び出し統合

### AC
- 正常時に指定URLへPOSTできる。
- タイムアウト/5xx/接続拒否でもメインループが継続する。
- ログに送信成否と `event_id` が記録される。

### DoD
- Dispatcherのユニットテスト（成功/失敗）がある。
- メイン処理非停止を手動またはテストで確認済み。

---

## Issue 3
### Title
`feat: dispatch webhook events on single-frame inference completion`

### Body
#### Background
従来モード（single）結果を外部連携対象にしたい。

#### Goal
`VLMService.process_frame()` 完了時に webhook dispatch を呼び出す。

#### Scope
- `src/live_vlm_webui/vlm_service.py`
- payloadに `mode=single` を付与
- `LIVE_VLM_WEBHOOK_MODE in {single,both}` のとき送信

#### Out of Scope
- マルチフレーム推論経路の送信

### AC
- single推論完了時のみイベントが送信される。
- Webhook無効時は一切送信しない。
- 既存の `current_response` 更新とWebUI表示が維持される。

### DoD
- single経路で送信ログとUI更新の両方が確認済み。
- エラー時も `vlm_response` が継続配信される。

---

## Issue 4
### Title
`feat: dispatch webhook events on multi-frame inference and fallback completion`

### Body
#### Background
マルチフレーム推論結果も外部連携対象に統一したい。

#### Goal
`VideoVLMPipeline.process_frame()` の最終結果確定点で送信する。

#### Scope
- `src/live_vlm_webui/video_vlm_pipeline.py`
- payloadに `mode=multi`、代表フレーム数を付与
- `LIVE_VLM_WEBHOOK_MODE in {multi,both}` のとき送信

#### Out of Scope
- 受信側の判定ロジック

### AC
- マルチ成功時にイベント送信される。
- fallback（逐次推論）時も送信される。
- 送信失敗してもパイプライン処理が継続する。

### DoD
- multi/fallback両ケースで送信を確認済み。
- WebUI表示と既存メトリクス更新に回帰がない。

---

## Issue 5
### Title
`docs: define webhook event payload schema v1`

### Body
#### Background
受信側の実装を安定化するため、payload仕様の固定化が必要。

#### Goal
Webhookイベントのv1スキーマを文書化する。

#### Scope
- `docs/development/webhook-events.md`（推奨）
- 必須/任意フィールド、例、互換性方針

#### Out of Scope
- 実際の送信実装

### AC
- v1 payloadの必須/任意項目が定義されている。
- バージョニング/後方互換ポリシーが明記されている。
- サンプルJSONが掲載されている。

### DoD
- ドキュメントのみで受信側が実装可能。
- チームレビューで合意済み。

---

## Issue 6
### Title
`feat(docker): add sample action-webhook receiver service for local demo`

### Body
#### Background
Webhook連携のデモを即確認する受信先が必要。

#### Goal
Docker Composeで起動できる受信サンプルサービスを追加する。

#### Scope
- 新規 `services/action-webhook/`（FastAPI最小構成）
- `POST /events` を受信してログ出力
- composeへのサービス定義追加

#### Out of Scope
- 本格的な通知連携（Slack/LINE/Email本番運用）

### AC
- `docker compose up` で受信サービスが起動する。
- live-vlm-webuiからのPOSTを受信ログで確認できる。
- 既存プロファイル動作を壊さない。

### DoD
- ローカルデモ手順がREADME_MODIFYに記載済み。
- 受信確認のスクリーンショットまたはログ例がある。

---

## Issue 7
### Title
`test: add resilience tests for webhook failure scenarios`

### Body
#### Background
非機能要件として「送信失敗でVLM処理を止めない」を保証したい。

#### Goal
Webhook送信失敗系のテストを追加する。

#### Scope
- `tests/unit/` にdispatcher失敗テスト
- `tests/integration/` に推論継続性テスト

#### Out of Scope
- 負荷試験・長時間耐久試験

### AC
- タイムアウト/5xx/接続拒否でテストが通る。
- 失敗後も `vlm_response` が継続配信される。
- 回帰として既存テストに重大影響がない。

### DoD
- CIまたはローカルで再現性ある結果が得られる。
- テスト失敗時の原因が追跡できるログがある。

---

## Issue 8
### Title
`docs: update operation guide for webhook enable/disable and rollback`

### Body
#### Background
プロトタイプ運用では切替手順の明確化が重要。

#### Goal
Webhook機能の有効化/無効化/切り戻し手順を文書化する。

#### Scope
- `README_MODIFY.md` 更新
- 必要なら `README.md` から導線追加

#### Out of Scope
- 実装コード変更

### AC
- 環境変数設定手順が明記されている。
- 失敗時の切り戻し手順（無効化 + 再起動）が記載されている。
- 動作確認チェックリストがある。

### DoD
- 新規メンバーがドキュメントのみで検証可能。
- 手順に曖昧さがない。

---

## GitHub操作ガイド（初心者向け）

以下は「Issue作成」「ブランチ作業」「Push」「PR作成」の最短手順。

### A. 事前準備（最初だけ）
1. GitHubアカウントで対象リポジトリにアクセスする。
2. 書き込み権限がない場合はForkする。
3. ローカルでリポジトリ直下へ移動する。

### B. Issue作成（Web UI）
1. GitHubの対象リポジトリを開く。
2. `Issues` タブを開く。
3. `New issue` を押す。
4. 上のテンプレートから `Title` と `Body` を貼る。
5. `Labels`（例: `enhancement`, `docs`, `backend`）を付与。
6. `Submit new issue` を押す。

### C. 開発ブランチ作成（ローカル）
```bash
cd live-vlm-webui
git checkout -b feat/webhook-dispatcher
```

### D. 変更のコミット
```bash
git status
git add <変更ファイル>
git commit -m "feat: add webhook dispatcher skeleton"
```

### E. GitHubへPush
```bash
git push -u origin feat/webhook-dispatcher
```

### F. Pull Request作成（Web UI）
1. GitHub上で `Compare & pull request` を押す。
2. PRタイトルを設定（例: `feat: add webhook dispatcher`）。
3. 説明に以下を記載:
   - 目的
   - 変更点
   - テスト結果
   - 関連Issue（`Closes #123`）
4. `Create pull request` を押す。

### G. レビュー対応
1. 指摘に応じてローカル修正。
2. 同じブランチに追加commitしてpush。
3. PR上で自動更新される。

### H. マージ後
1. GitHubでPRをマージ。
2. ローカルでmainへ戻る。
```bash
git checkout main
git pull
```

---

## 補足（今回の運用方針に合わせた最小実践）
- いまはホスト環境で直接修正運用でも問題ない。
- ただし変更履歴を残すため、最低限「Issue作成 -> ブランチ -> PR」を推奨。
- まずは Issue 1 -> Issue 2 -> Issue 3 の順で小さく進めるとレビューしやすい。
