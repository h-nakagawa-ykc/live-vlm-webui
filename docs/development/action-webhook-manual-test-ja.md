# Action Webhook 手動検証ガイド（PR-3時点）

## 目的
- `services/action-webhook` のルール評価・アクション実行が意図どおり動作することを手動で確認する。
- `ACTION_RULES_FILE` 差し替え時に、正常読込・フォールバックが機能することを確認する。
- 旧MVP（固定ルール版）と、PR-3（ルール外部化版）の判定結果が一致することを確認する。

## 前提
- action-webhook が起動している（例: `http://localhost:8081`）。
- 環境変数例:
  - `ACTION_RULES_ENABLED=true`
  - `ACTION_RULES_FILE=/app/rule_configs/rules.yaml`
- 参照ファイル:
  - `services/action-webhook/rule_configs/rules.yaml`
  - `services/action-webhook/rules.py`
  - `docs/development/webhook-events.md`

## 1. health確認
`/healthz` は action-webhook コンテナの生存確認用エンドポイント。  
用途は「Kubernetes/Docker監視などによる死活監視（liveness/readiness相当）」であり、  
`/events` のルール評価ロジックや外部連携（Slack/IP機器）の成否までは保証しない。

確認観点:
- HTTP 200 が返る: プロセスが起動し API が応答可能
- 返却JSON `{"status":"ok"}`: アプリ層の最小ヘルスが正常

補足:
- 実運用では `/healthz` に加えて、`/events` への疎通テスト（POST）も別途実施すること。

```bash
BASE=http://localhost:8081
curl -sS "$BASE/healthz"
```

## 2. 「テストpayloadを3種類」の意味（想定と目的）
以下3ケースは、`RuleEvaluator` が値を抽出する経路の違いを確認するための最小セット。

1. `answer` が payload 直値にあるケース  
目的: 最優先の抽出経路（payload直値）を確認する。

2. `text` が JSON文字列のケース  
目的: payload直値が無い場合に `text` JSONから値を抽出できることを確認する。

3. 生テキストのみのケース（キーワード判定）  
目的: 構造化データが無くても文字列マッチでルール発火できることを確認する。

この3ケースで確認している本質:
- webhook受信側が、**完全に理想的な構造化応答だけでなく**、非構造/部分構造の応答にも一定の耐性があること
- ルール判定が「payload直値」「text内JSON」「生テキスト」の順にフォールバックして解釈できること

## 2.1 これらのpayloadは何を想定しているか
- 想定している入力は、`live_vlm_webui` 側が `/events` へ送る webhook payload（`event_type=vlm_inference_result`）。
- `text` は VLM の生応答文字列であり、プロンプト次第で JSON 風にも自然文にもなり得る。
- そのため受信側（action-webhook）は、厳密JSONのみを前提にせず、複数の抽出経路を持つ設計にしている。

## 2.2 `text` / `answer` の確実性について
- `docs/development/webhook-events.md` の共通必須項目として `text` は定義されている。
- ただし `text` の中身が常に JSON で、かつ `answer` を常に含む保証はない。
- `answer` や `risk_score` は optional であり、未設定・形式不正・非JSON応答の可能性を前提に扱う。

受信側の現行動作（PR-3時点）:
- `answer` 抽出順: payload直値 `answer` -> `text` がJSON objectなら `text.answer` -> 生テキストから `yes/no` 正規表現
- `risk_score` 抽出順: payload直値 `risk_score` -> `text` JSON内 `risk_score`
- いずれも取得できなければ `None` として扱い、該当ルールは不一致になる

## 3. 基本3ケースのpayload例

### 3-1. `answer` が payload 直値（yes）
期待: `rule_yes` が一致し、`actions` は `["slack","device"]`。
```bash
curl -sS -X POST "$BASE/events" -H 'Content-Type: application/json' -d '{
  "event_id":"t-yes-direct-1",
  "event_type":"vlm_inference_result",
  "mode":"single",
  "text":"normal",
  "answer":"yes"
}'
```

### 3-2. `text` が JSON文字列（answer=no）
期待: `rule_no` が一致し、`actions` は `["slack"]`。
```bash
curl -sS -X POST "$BASE/events" -H 'Content-Type: application/json' -d '{
  "event_id":"t-text-json-1",
  "event_type":"vlm_inference_result",
  "mode":"single",
  "text":"{\"answer\":\"no\",\"risk_score\":0.88,\"labels\":[\"smoke\"]}"
}'
```

### 3-3. 生テキストのみ（キーワード）
期待: `rule_keyword_alert` が一致し、`actions` は `["slack"]`。
```bash
curl -sS -X POST "$BASE/events" -H 'Content-Type: application/json' -d '{
  "event_id":"t-keyword-1",
  "event_type":"vlm_inference_result",
  "mode":"single",
  "text":"ALERT: smoke detected near gate"
}'
```

## 4. 他パターンのpayload例

### 4-1. `risk_score_gte` 判定（payload直値）
期待: `rule_risk_high` が一致し、`actions` は `["slack"]`。
```bash
curl -sS -X POST "$BASE/events" -H 'Content-Type: application/json' -d '{
  "event_id":"t-risk-1",
  "event_type":"vlm_inference_result",
  "mode":"single",
  "text":"normal",
  "risk_score":0.91
}'
```

### 4-2. `risk_score_gte` 判定（text JSONから抽出）
期待: `rule_risk_high` が一致し、`actions` は `["slack"]`。
```bash
curl -sS -X POST "$BASE/events" -H 'Content-Type: application/json' -d '{
  "event_id":"t-risk-json-1",
  "event_type":"vlm_inference_result",
  "mode":"single",
  "text":"{\"risk_score\":0.90}"
}'
```

### 4-3. 複数ルール同時一致
期待: `rule_yes` と `rule_risk_high` が一致し、`actions` は重複除去され `["slack","device"]`。
```bash
curl -sS -X POST "$BASE/events" -H 'Content-Type: application/json' -d '{
  "event_id":"t-multi-match-1",
  "event_type":"vlm_inference_result",
  "mode":"single",
  "text":"{\"risk_score\":0.95}",
  "answer":"yes"
}'
```

### 4-4. どのルールにも一致しない
期待: `matched_rule_ids=[]`、`actions=[]`。
```bash
curl -sS -X POST "$BASE/events" -H 'Content-Type: application/json' -d '{
  "event_id":"t-no-match-1",
  "event_type":"vlm_inference_result",
  "mode":"single",
  "text":"all clear"
}'
```

### 4-5. payload直値とtext JSONが矛盾する（優先順位確認）
期待: payload直値 `answer=no` が優先され、`rule_no` が一致する。
```bash
curl -sS -X POST "$BASE/events" -H 'Content-Type: application/json' -d '{
  "event_id":"t-priority-answer-1",
  "event_type":"vlm_inference_result",
  "mode":"single",
  "answer":"no",
  "text":"{\"answer\":\"yes\",\"risk_score\":0.90}"
}'
```

### 4-6. `text` がJSONではないが yes/no を含む
期待: 正規表現抽出で `answer=yes` となり `rule_yes` が一致する。
```bash
curl -sS -X POST "$BASE/events" -H 'Content-Type: application/json' -d '{
  "event_id":"t-yes-regex-1",
  "event_type":"vlm_inference_result",
  "mode":"single",
  "text":"Final decision: YES. no threat found in frame."
}'
```

### 4-7. `risk_score` の形式不正
期待: `risk_score` は無効として扱われ、`rule_risk_high` は不一致。
```bash
curl -sS -X POST "$BASE/events" -H 'Content-Type: application/json' -d '{
  "event_id":"t-risk-invalid-1",
  "event_type":"vlm_inference_result",
  "mode":"single",
  "text":"{\"risk_score\":\"high\"}"
}'
```

## 5. `ACTION_RULES_FILE` 差し替えとフォールバック確認

### 5-1. 正常読込
- `ACTION_RULES_FILE=/app/rule_configs/rules.yaml` で起動し、上記payloadで判定確認。

### 5-2. ファイル未存在（フォールバック）
- 例: `ACTION_RULES_FILE=/app/rule_configs/not-found.yaml`
- 期待:
  - 起動が継続する
  - ログに「rules file not found / fallback」系の警告
  - 判定はデフォルト固定ルール相当で動作

### 5-3. YAML不正（フォールバック）
- 不正YAMLを指定して起動。
- 期待:
  - 起動継続
  - ログにロード失敗警告
  - デフォルト固定ルール相当にフォールバック

## 6. 「旧MVP動作と一致」の確認方法
意味: 同一payloadに対して、旧MVP相当と同じ判定・同じ実行アクションであること。

確認対象:
- `matched_rule_ids`（どの条件に一致したか）
- `actions`（`slack` / `device`）

例:
- payloadが `answer=yes` のとき
  - 一致すべき結果: `matched_rule_ids` に `rule_yes`、`actions` は `["slack","device"]`
- payloadが `answer=no` のとき
  - 一致すべき結果: `matched_rule_ids` に `rule_no`、`actions` は `["slack"]`

## 7. `RuleEvaluator` の責務確認（コードレビュー観点）
これは基本的に目視確認で実施する。

確認ポイント:
1. 評価と実行が分離されている  
   - `rules.py` は判定のみを担当  
   - `actions/slack.py` `actions/device_http.py` は実行のみを担当
2. 条件がルール定義ベース  
   - `rule_configs/rules.yaml` の変更で挙動変更できる
3. 追加条件が拡張しやすい  
   - `if/else` 乱立ではなく、`when` 条件の拡張で対応可能な構造

`when` の現行解釈（PR-3時点）:
- `answer_in`: 値のいずれかに一致したら真（大文字小文字は正規化）
- `text_contains_any`: キーワードのいずれかを含めば真
- `risk_score_gte`: `risk_score >= threshold` なら真（`>` ではなく `>=`）
  - threshold に `${RISK_THRESHOLD}` を書くと、環境変数 `RISK_THRESHOLD` を参照

例:
```yaml
rules:
  - id: rule_yes
    when:
      answer_in: ["yes"]
    actions: ["slack", "device"]
```

補足:
- 1ルール内に複数条件がある場合は AND 評価（すべて満たしたとき一致）。
- 一致した複数ルールの `actions` は重複除去して実行する。

## 8. 補足: labels条件の扱い（PR-3時点）
- 現時点の `RuleEvaluator` は `labels` を判定条件に使用していない。
- そのため、`labels` 優先順位（payload > text JSON）確認はPR-3の必須観点ではない。
- 今後は正規化層（例: PayloadNormalizer）を導入し、`labels_any` や `labels_all` の条件追加を想定する。

## 9. `RuleEvaluator` 今後の実装方針（展望）
1. 正規化層の導入  
   - payload/text JSON/生テキストを単一の正規化構造へ集約
2. 条件演算子の拡張  
   - 例: `labels_any`, `labels_all`, `text_regex`, `camera_id_in`, `mode_in`
3. 合成条件  
   - `all_of` / `any_of` / `not` を導入して複雑ルールを宣言的に記述
4. 可観測性の強化  
   - 「なぜ一致/不一致だったか」をレスポンス・ログに構造化出力
5. 安全性強化  
   - 無効ルールのスキップ理由を明示し、誤設定時のデバッグ性を向上
