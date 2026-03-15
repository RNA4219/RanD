# RanD Requirements

## 0. 文書情報

- 文書種別: requirements
- 状態: active
- 対象: `RanD` ルート、`research-runtime`、`kestra/flows`
- 参照元: [next-implementation-priorities.md](/Users/ryo-n/Codex_dev/RanD/docs/next-implementation-priorities.md), [architecture.md](/Users/ryo-n/Codex_dev/RanD/docs/architecture.md)

## 1. 目的

RanD は、R&D エージェントを構成する OSS 群を固定コミットで導入し、`research -> insight -> gate -> plan -> sync` のパイプラインを定期実行または外部イベント起点で運転するための親リポジトリである。

本要求定義の目的は、次の 3 点を「実装してよい要求」として固定することにある。

1. 常時運転できる制御面を持つこと
2. 過去状態を踏まえて調査と判断を繰り返せること
3. 結果を外部へ返し、仕事へ変換できること

## 2. 背景と問題

現状の RanD は、導入層、ローカル実行ランタイム、Kestra flow の初期実装を持つ。一方で、本番運用に必要な要求として以下が未固定または弱い。

- state を正本から読み直して run に反映する契約
- durable dedupe、retry、manual replay、resend の要件
- `agent-taskstate`、`memx-resolver`、`tracker-bridge-materials` との入出力境界
- Kestra から起動したときの正常系・異常系の流れ
- どの状態になれば「運用可能」とみなすかの受け入れ基準

## 3. スコープ

### 3.1 In Scope

- `r-and-d-agent-installer` による固定版導入
- `research-runtime` による state-aware な research 実行
- `kestra/flows` による webhook / schedule 起動
- `agent-taskstate` を正本とした run / task state 管理
- `memx-resolver` を正本とした read / journal / docs context 管理
- `tracker-bridge-materials` 向け sync payload 生成
- `insight-agent`、`experiment-gate`、`Roadmap-Design-Skill` との worker chaining
- Misskey / tracker / planning 層への handoff 契約

### 3.2 Out of Scope

- Misskey bridge 自体の実装詳細
- `agent-taskstate` のスキーマ変更
- `memx-resolver` の API 追加実装
- tracker 先 SaaS 側の認証・権限設計の詳細
- UI ダッシュボード実装

## 4. 利害関係者

| 利害関係者 | 関心事 |
| --- | --- |
| RanD 運用者 | 自律巡回、失敗回復、再実行、成果物の追跡 |
| R&D 実務担当 | 論文・ニュースの優先順位、Go/Hold 判定、次アクション |
| インフラ/運用担当 | Kestra での常時運転、再送、重複排除、タイムアウト |
| 外部連携担当 | tracker 起票、Misskey 通知、PRD/roadmap への handoff |

## 5. 成功条件

RanD は次を満たすとき、MVP として成立したとみなす。

1. webhook または schedule のどちらからでも research flow を起動できる
2. 実行前に state を読み、実行後に state を更新できる
3. 既読 item を gate 優先対象から外せる
4. `report`, `insight`, `gate`, `state context`, `tracker sync` を保存できる
5. 失敗時に `needs_review` または `failed` で残り、再送/再開へつなげられる

## 6. システム境界と正本

| 領域 | 正本 | RanD の責務 |
| --- | --- | --- |
| 実行制御 | `Kestra` | flow 定義と runtime 呼び出しを提供する |
| 外部イベント入口 | `pulse-kestra` | 受け口ではなく受け先として接続する |
| task / run state | `agent-taskstate` | state の local snapshot と連携契約を持つ |
| knowledge / read history | `memx-resolver` | read / journal を参照し、必要 payload を生成する |
| insight | `insight-agent` | worker 入力を正規化して渡す |
| gate | `experiment-gate` | high priority 候補だけを渡す |
| tracker sync | `tracker-bridge-materials` | tracker 向け payload を生成する |
| planning / PRD | `Roadmap-Design-Skill`, `ai-product-requirement-document` | Go 判定テーマを handoff する |

## 7. ユースケース

### UC-01 定期論文監視

- actor: Kestra schedule
- trigger: 毎日夜間の arXiv 巡回
- outcome: 新規論文を優先度付きで収集し、Go 候補を生成する

### UC-02 定期 AI ニュース巡回

- actor: Kestra schedule
- trigger: 毎朝の公式ニュース巡回
- outcome: 既読記事を避けつつ、差分あるニュースだけを上位に出す

### UC-03 mention 起点調査

- actor: `pulse-kestra`
- trigger: Misskey mention
- outcome: research flow を起動し、返答と state 更新を行う

### UC-04 障害回復

- actor: heartbeat / operator
- trigger: stuck task、reply 失敗、tracker 同期失敗
- outcome: retry、replay、resend のいずれかに振り分ける

## 8. 機能要求

### 8.1 制御面

| ID | 要求 | 測定条件 |
| --- | --- | --- |
| FR-C01 | webhook と schedule の両方で Kestra flow を起動できること | 2 種類の trigger を持つ flow が存在する |
| FR-C02 | research flow は `event_type`, `preset`, `max_items`, `source` を入力として受け取れること | webhook payload の必須/任意項目が仕様化されている |
| FR-C03 | task state は `queued -> running -> done/needs_review/failed` を記録できること | `report.json` と state snapshot に遷移結果が残る |
| FR-C04 | durable dedupe を考慮し、少なくとも `idempotency key`, `preset`, `url/title` で重複判定できること | 同一 URL 再投入時に `seen_before=true` が立つ |
| FR-C05 | stuck task、reply 失敗、worker 失敗に対して replay/resend/retry の導線を持つこと | flow または運用手順として明記されている |
| FR-C06 | `llm-guard` は入口だけでなく出口投稿前にも挟めること | flow 設計上の insertion point が定義されている |
| FR-C07 | control plane は `research -> insight -> gate -> sync -> notify` の chaining を表現できること | sequence と flow で順序が固定されている |
| FR-C08 | heartbeat は定期巡回と回復監視の両方を起動できること | 日次巡回 flow と回復 flow の少なくとも 2 系統が定義される |

### 8.2 研究・判断面

| ID | 要求 | 測定条件 |
| --- | --- | --- |
| FR-R01 | source preset ごとに seed source を定義できること | preset JSON が存在する |
| FR-R02 | 収集結果は `NormalizedItem` に正規化されること | `report.json.collected_items[*]` が共通キーを持つ |
| FR-R03 | 実行前に同一 preset の過去 task と memory entry を取得できること | `state_context.before` に `previous_run_count`, `known_urls`, `open_tasks` が入る |
| FR-R04 | 既知 URL は `seen_before=true` とし、priority と gate 対象に反映すること | 既読 item の `high_priority=false` を確認できる |
| FR-R05 | insight 抽出は `claims`, `limitations`, `open_questions` 相当を扱えること | insight worker の出力参照が保存される |
| FR-R06 | gate は `go`, `hold`, `no_go` と次アクションを返せること | gate 出力が 3 値または fallback と next step を持つ |
| FR-R07 | Go 判定テーマだけを planning/PRD 層へ渡せること | handoff payload 条件が定義されている |
| FR-R08 | evidence gap を再探索条件として次 run に戻せること | open question / missing evidence を report 参照で保持する |

### 8.3 外界反映面

| ID | 要求 | 測定条件 |
| --- | --- | --- |
| FR-E01 | mention 起点処理は reply または失敗状態で閉じること | reply_state 相当の結果を残す |
| FR-E02 | heartbeat 起点処理は自律投稿または通知 payload を生成できること | schedule flow と通知 insertion point がある |
| FR-E03 | tracker 同期 payload は `tracker_connection`, `remote_ref`, `payload_json` 相当へ写像可能であること | `tracker_sync.json` に最小項目が保存される |
| FR-E04 | Go 判定結果は roadmap / PRD handoff に昇格できること | next action に planning handoff 条件がある |
| FR-E05 | 1 run あたり Markdown と JSON 両方の成果物を残すこと | `report.md`, `report.json` が生成される |
| FR-E06 | 実行結果は再参照可能な形で保存されること | run directory に `meta`, `gate`, `insight`, `state_context` が残る |

## 9. 状態管理要求

| ID | 要求 | 測定条件 |
| --- | --- | --- |
| SR-01 | run 開始前に state snapshot を取得すること | `state_context.before` が存在する |
| SR-02 | run 中に task state を更新すること | `taskstate.json` に `queued`, `running`, `done/needs_review` が記録される |
| SR-03 | run 完了後に state snapshot を再取得すること | `state_context.after` が存在する |
| SR-04 | memory journal に source と要約を残すこと | `memx-journal.json` に entry が追加される |
| SR-05 | tracker sync event を別ログで残すこと | `tracker-sync.json` に event が追加される |
| SR-06 | state 読み書き失敗時は `needs_review` または `failed` へ落とすこと | 失敗時の状態が定義されている |

## 10. 非機能要求

| ID | 要求 | 測定条件 |
| --- | --- | --- |
| NFR-01 | ローカル実行と Kestra 実行の両方をサポートすること | bat 入口と Kestra flow が両方存在する |
| NFR-02 | LLM 実行タイムアウトは 600 秒以上、収集タイムアウトは 180 秒以上を下限とすること | runtime config に数値が入っている |
| NFR-03 | すべての成果物は監査可能な JSON / Markdown として保存すること | run directory の artifact 一覧が固定されている |
| NFR-04 | 外部 repo 更新の影響を受けず再現導入できること | `pinnedCommit` に固定されている |
| NFR-05 | tracker 側障害があっても research run 自体は完了または review へ落ちること | tracker は optional output であると明示されている |
| NFR-06 | tracker は内部 state の正本にならないこと | requirements と spec の両方に明記されている |

## 11. インターフェース要求

### 11.1 Kestra -> research-runtime

```json
{
  "event_type": "manual|schedule|heartbeat",
  "preset": "paper_arxiv_ai_recent",
  "max_items": 8,
  "source": "kestra.schedule.paper_arxiv_ai_recent"
}
```

### 11.2 research-runtime -> agent-taskstate snapshot

- 入力として読むもの
  - `task_id`
  - `run_id`
  - `preset`
  - `status`
  - `updated_at`
  - `summary`
- 少なくとも same preset の過去 task と open task を取り出せること

### 11.3 research-runtime -> memx-resolver journal

- 少なくとも次を含めること
  - `entry_id`
  - `scope=rand:<preset>`
  - `recorded_at`
  - `summary`
  - `sources[]`
  - `artifacts`

### 11.4 research-runtime -> tracker-bridge-materials sync payload

- 少なくとも次を含めること
  - `sync_id`
  - `preset`
  - `items[].title`
  - `items[].url`
  - `items[].kind`
  - `gate_recommendations[].verdict`
  - `gate_recommendations[].recommended_action`

## 12. 異常系要求

- ER-01: insight worker import 失敗時は fallback insight を返し、run を継続する
- ER-02: gate worker 失敗時は fallback gate を返し、run を `needs_review` 候補として残せる
- ER-03: source fetch 失敗時は source 名付き error を `meta.errors` に残す
- ER-04: tracker sync 失敗時は research artifact 保存を優先し、tracker だけを別失敗として記録する
- ER-05: state snapshot 取得失敗時は run を `failed` または `needs_review` とする

## 13. 受け入れ条件

- AC-01: `research-manual-run`, `research-ai-watch-daily`, `research-arxiv-nightly` の 3 flow が存在する
- AC-02: `run-once` 実行結果に `state_context.before` と `state_context.after` が含まれる
- AC-03: 既知 URL を含む入力で `seen_before=true` と `high_priority=false` が確認できる
- AC-04: `report.md`, `report.json`, `insight.json`, `gate.json`, `meta.json`, `memx_journal.json`, `tracker_sync.json`, `state_context.json` が保存される
- AC-05: `env-check` で `open_deep_research`, `insight-agent`, `experiment-gate`, `agent-taskstate`, `memx-resolver`, `tracker-bridge-materials` の利用可否を確認できる
- AC-06: tracker を外しても research run 自体の実行結果は保存される

## 14. 優先順位

- P1: 制御面の完成
- P2: 研究・判断面の多段化
- P3: 外界反映面の完成

本優先順位は [next-implementation-priorities.md](/Users/ryo-n/Codex_dev/RanD/docs/next-implementation-priorities.md) の結論を実装可能な要求へ落としたものである。
