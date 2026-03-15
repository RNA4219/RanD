# RanD Requirements

## 0. 文書情報

- 文書種別: requirements
- 状態: active
- 対象: `RanD` ルート、`research-runtime`、`kestra/flows`
- 参照元: [next-implementation-priorities.md](next-implementation-priorities.md), [architecture.md](architecture.md)

## 1. 目的

RanD は、R&D エージェントを構成する OSS 群を固定コミットで導入し、`research -> insight -> gate -> sync` をローカルまたは Kestra から反復実行するための親リポジトリである。

本要求定義の目的は次を固定することにある。

1. 他人の環境でも導入再現できること
2. state を読んで次の run に反映できること
3. 依存失敗を `degraded` / `failed` として明示できること
4. 成果物 JSON を版管理しながら進化できること

## 2. スコープ

### 2.1 In Scope

- `r-and-d-agent-installer` による pinned install
- `CODEX_DEV_ROOT` と override を使う local path 解決
- `research-runtime` による state-aware な research 実行
- `status=ok|degraded|failed` の明示
- `schema_version` を持つ artifact 保存
- fixture ベースの fetcher 回帰テスト
- heartbeat / preset 選択規則の設定化と文書化
- `agent-taskstate`, `memx-resolver`, `tracker-bridge-materials` との state / sync 連携

### 2.2 Out of Scope

- 各 peer repo 自体の API 拡張
- tracker SaaS 側の認証設計
- UI ダッシュボード実装

## 3. 成功条件

1. installer がローカル絶対パスに依存せずに動く
2. `python -m unittest discover tests` が repo 単体で通る
3. heartbeat の preset 選択が設定ファイルと docs に固定される
4. `report.json` が `status`, `status_reason`, `schema_version`, `state_context`, `artifacts` を持つ
5. `taskstate` へ `done / needs_review / failed` が正しく写る

## 4. 機能要求

### 4.1 Installer

| ID | 要求 | 測定条件 |
| --- | --- | --- |
| FR-I01 | manifest は絶対 `localPath` を持たず `pathKey`, `relativePath`, `envVar` で local path を解決できること | `components.json` に OS ユーザー依存の絶対パスが存在しない |
| FR-I02 | local path 解決優先順位は override JSON > repo 個別 env > `CODEX_DEV_ROOT + relativePath` > remoteUrl とすること | README と scripts の動作が一致する |
| FR-I03 | `-Mode local` は未解決 component を warning 付きで skip すること | status / install の出力で確認できる |
| FR-I04 | `-Mode auto` は未解決 component だけ remote fallback すること | local 不在 component が remote clone される |
| FR-I05 | `-Mode remote` は local path を見ず remote clone すること | install ログで確認できる |

### 4.2 Runtime / State

| ID | 要求 | 測定条件 |
| --- | --- | --- |
| FR-R01 | run 前に `taskstate` と `memx` を読み `ExecutionContext` を組み立てること | `state_context.before` が存在する |
| FR-R02 | 既知 URL は `seen_before=true` とし `high_priority=false` にできること | 回帰テストで確認できる |
| FR-R03 | Insight / Gate / Memx / Tracker の結果 payload は `status` と `error` を持つこと | 各 artifact にキーが存在する |
| FR-R04 | fallback を返す場合でも run 全体は `degraded` または `failed` を返すこと | `report.json.status` と `status_reason` が存在する |
| FR-R05 | `ok -> done`, `degraded -> needs_review`, `failed -> failed` の写像を taskstate に保存すること | `taskstate.json` で確認できる |
| FR-R06 | source 全滅、state 読み書き失敗、report 保存失敗は `failed` で終了すること | unit test または実 run で確認できる |
| FR-R07 | source 一部失敗、Insight/Gate/Memx/Tracker の個別失敗は `degraded` で終了すること | unit test または実 run で確認できる |

### 4.3 Artifact / Schema

| ID | 要求 | 測定条件 |
| --- | --- | --- |
| FR-A01 | `report.json`, `state_context.json`, `tracker_sync.json`, `memx_journal.json`, `meta.json` は `schema_version` を持つこと | run directory の JSON を確認できる |
| FR-A02 | `report.json` は `schema_version`, `status`, `status_reason`, `state_context`, `artifacts`, `dependency_health` を必須とすること | report schema 検証テストが通る |
| FR-A03 | schema 互換方針を文書化すること | specification に policy がある |

### 4.4 Fetcher / Schedule

| ID | 要求 | 測定条件 |
| --- | --- | --- |
| FR-F01 | fetcher 回帰テストは fixture ベースで行うこと | `tests/fixtures/` が存在する |
| FR-F02 | arXiv / RSS / generic link の正常系と壊れ方検知があること | `test_fetchers.py` が通る |
| FR-F03 | heartbeat の preset 選択規則は設定ファイルを正本とすること | `configs/heartbeat.json` が存在する |
| FR-F04 | 朝 / 夜 / default の選択規則を docs と README に明記すること | 文書に表がある |
| FR-F05 | composed preset は child status を集約すること | specification と実装が一致する |

## 5. 非機能要求

| ID | 要求 | 測定条件 |
| --- | --- | --- |
| NFR-01 | README は Quickstart を最上部に持つこと | ルート README 先頭で確認できる |
| NFR-02 | README / docs は OS ユーザー固有のローカル絶対パスを含まないこと | 対象文書にユーザー依存のローカル絶対パスがない |
| NFR-03 | `research-runtime` は単体依存と workspace 依存を分けて説明すること | runtime README に表現がある |
| NFR-04 | fixture テストを正本にし、live fetch を受け入れ条件にしないこと | evaluation に記載がある |

## 6. 受け入れ条件

- AC-01: installer manifest に OS ユーザー依存の絶対 path がない
- AC-02: `heartbeat --dry-run` が JST と preset を返す
- AC-03: `python -m unittest discover tests` が通る
- AC-04: `report.json` に `schema_version`, `status`, `status_reason`, `state_context`, `artifacts` が含まれる
- AC-05: `state_context.json` に `schema_version`, `before`, `after` が含まれる
- AC-06: `memx_journal.json` と `tracker_sync.json` の root と entry/event に `schema_version` が入る
- AC-07: README に Quickstart、heartbeat 選択規則、artifact 契約がある
