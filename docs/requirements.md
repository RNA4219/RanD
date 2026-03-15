# RanD Requirements

## 1. 目的

本書は [next-implementation-priorities.md](/Users/ryo-n/Codex_dev/RanD/docs/next-implementation-priorities.md) を、実装可能な要件へ落とした要求定義である。

RanD の目的は、R&D Agent の構成要素を単に並べることではなく、以下を継続運用できるようにすることにある。

- 外部イベントまたは定期実行で起動できる
- 調査、洞察、評価、計画、同期を一連で実行できる
- 実行前後の状態を把握し、再開や再送ができる
- 結果を Misskey や tracker など外界へ返せる

## 2. スコープ

本要求定義の対象は次の 3 層である。

1. 制御面
2. 研究・判断面
3. 外界反映面

対象リポジトリは `RanD` を中心に、`pulse-kestra`、`kestra`、`agent-taskstate`、`memx-resolver`、`insight-agent`、`experiment-gate`、`tracker-bridge-materials`、`Roadmap-Design-Skill`、`ai-product-requirement-document` を含む。

## 3. 前提

- `agent-taskstate` は内部状態の正本である
- `memx-resolver` は知識参照と読了記録の正本である
- `Kestra` は実行制御の正本である
- `pulse-kestra` は外部イベントと Kestra の橋渡しを担う
- `RanD/research-runtime` はローカル実行および Kestra 実行から呼ばれる研究 worker である

## 4. ユースケース

### UC-01 論文監視

- 定期実行で `arXiv cs.AI recent` を巡回する
- 過去に処理済みの論文を踏まえて優先度を付け直す
- Go 判定のものを次アクションへつなぐ

### UC-02 AI ニュース巡回

- OpenAI / Anthropic / DeepMind / Google AI Blog を定期巡回する
- 既読記事や過去 topic との重複を考慮する
- 必要に応じて外部へ通知または task 化する

### UC-03 mention 起点の即応

- Misskey mention を受信する
- Guard を通して worker chain を起動する
- 応答、state 更新、必要なら tracker 同期まで行う

### UC-04 障害回復

- stuck task を検知して review または replay へ回す
- 投稿失敗や通知失敗時に再送できる
- idempotency を保ったまま再開できる

## 5. 機能要求

### 5.1 制御面要求

- FR-C01: `pulse-kestra` は mention / webhook / cron / heartbeat を単一イベントモデルで受け取り、Kestra flow 起動要求へ正規化できなければならない。
- FR-C02: `Kestra` は RanD の research 系 flow を schedule と webhook の両方で起動できなければならない。
- FR-C03: 実行開始時に `agent-taskstate` へ task / run を作成または更新し、少なくとも `queued / running / done / needs_review / failed` を扱えなければならない。
- FR-C04: 入力と外部投稿前の両方で `llm-guard` を適用できなければならない。
- FR-C05: durable dedupe により、同一イベント、同一 URL、同一 idempotency key に対する二重実行を抑止できなければならない。
- FR-C06: stuck task、投稿失敗、worker 失敗に対して retry / replay / resend を実行できなければならない。
- FR-C07: control plane は worker chaining をサポートし、少なくとも `research -> insight -> gate -> sync -> notify` の順序を表現できなければならない。
- FR-C08: heartbeat flow は定期巡回の本体として動作し、topic watch と回復監視を起動できなければならない。

### 5.2 研究・判断面要求

- FR-R01: `open_deep_research` を利用する探索 worker は、preset ごとに定義された seed source を巡回できなければならない。
- FR-R02: 収集結果は `NormalizedItem` 相当の共通形式へ正規化されなければならない。
- FR-R03: 実行前に `agent-taskstate` と `memx-resolver` 由来の状態を読み、既読 URL、過去 run、未完了 task を把握しなければならない。
- FR-R04: 既知 item は `seen_before` として扱い、優先度や後続 gate 対象に反映されなければならない。
- FR-R05: `insight-agent` は調査 bundle から `claims / assumptions / limitations / insights / open_questions` を抽出できなければならない。
- FR-R06: `experiment-gate` は `go / hold / no_go` と次アクション推奨を返し、ワークフロー分岐に利用できなければならない。
- FR-R07: 反証または evidence gap の収集段を追加可能な構成でなければならない。
- FR-R08: Go 判定されたテーマは planning / PRD 層へ渡せなければならない。

### 5.3 外界反映面要求

- FR-E01: mention 起点の処理は、最終的に Misskey reply まで閉路化されなければならない。
- FR-E02: heartbeat 起点の処理は、自律投稿や巡回通知へ接続できなければならない。
- FR-E03: `tracker-bridge-materials` は Go / Hold の結果を外部 tracker 向け payload に変換し、実送信可能な形式で保持しなければならない。
- FR-E04: `Roadmap-Design-Skill` と PRD 層は、Go 判定のテーマを execution plan と requirement 文書へ昇格できなければならない。
- FR-E05: 成果物は人間向けレポートと機械向け JSON の両方で保存されなければならない。
- FR-E06: 実行結果は少なくとも `report`, `gate`, `insight`, `state snapshot`, `tracker sync` を再参照可能な形で保存しなければならない。

## 6. 状態管理要求

- SR-01: すべての run は開始前の state snapshot を取得しなければならない。
- SR-02: run 中に task state は段階遷移を記録しなければならない。
- SR-03: run 完了後に state snapshot を再取得し、before / after 差分を保存しなければならない。
- SR-04: `memx-resolver` 側には journal として source 群、要約、artifact 参照を残さなければならない。
- SR-05: state の読み書きに失敗した場合、run は `needs_review` または `failed` として残らなければならない。

## 7. 非機能要求

- NFR-01: run はタイムアウトや一時失敗に対して再試行可能でなければならない。
- NFR-02: 入口と出口の両方で安全ガードを挟める構成でなければならない。
- NFR-03: 主要 flow はローカル bat 実行と Kestra 実行の両方をサポートしなければならない。
- NFR-04: 成果物、state、外部同期 payload は監査可能な形で保存されなければならない。
- NFR-05: コンポーネントは固定コミットで再現可能に導入されなければならない。
- NFR-06: 既読判定、重複排除、再送は idempotent でなければならない。

## 8. 受け入れ条件

- AC-01: `Kestra` から `research-runtime` を起動する flow 定義が存在する。
- AC-02: `research-runtime` は実行前に task state と memory state を読み、実行後に更新する。
- AC-03: `state_context.json` または同等の before / after snapshot が生成される。
- AC-04: `paper_arxiv_ai_recent` と `ai_watch_daily` の両方に対応する flow が存在する。
- AC-05: `report.json` に collected items, state context, gate / insight の参照が含まれる。
- AC-06: テストまたは検証手順で、state-aware な run が壊れていないことを確認できる。

## 9. 優先順位

- P1: 制御面の完成
- P2: 研究・判断面の多段化
- P3: 外界反映面の完成

この順序は [next-implementation-priorities.md](/Users/ryo-n/Codex_dev/RanD/docs/next-implementation-priorities.md) の結論に従う。
