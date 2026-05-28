---
bb_acceptance_id: BB-20260528-01
task_id: TASK-20260528-01
acceptance_id: AC-20260528-01
intent_id: INT-CTG-001
owner: rand
status: go
profile: standard
executed_at: 2026-05-28
tooling:
  - manual-bb-test-harness
  - code-to-gate v1.3.0
---

# Code-to-gate hardening manual BB acceptance

## Intake Status

- status: ok
- scope:
  - atomic write 共通化
  - `state_store.py` / memx / tracker writer の永続化境界
  - `integrations.py` の責務分割
  - release gate への Code-to-gate 追加
- assumptions:
  - fixture ベースの `kano_requirements_offline_eval` を、live fetch なしの black-box 代表経路として扱う。
  - Misskey / tracker 実送信、Kestra 本格実行、外部 LLM provider は今回の検収範囲外。
- blockers:
  - なし

## 根拠付き観点

| id | title | view | techniques | source | rationale |
|---|---|---|---|---|---|
| OBS-001 | atomic write が既存 target を壊さない | state / data / regression | 状態遷移、異常系、回帰 | `TASK-20260528-01` P0、`tests/test_io_utils.py` | 永続化失敗時に state / artifact 破損を出さないことが IPO レベルの最低境界。 |
| OBS-002 | cleanup は target parent 配下の temp のみに限定される | data / rule | デシジョン、負例 | `TASK-20260528-01` P0、Code-to-gate `UNSAFE_DELETE` | 任意削除に見える操作を境界検証と静的 gate で閉じる必要がある。 |
| OBS-003 | public import 互換が維持される | regression | 直接回帰、契約確認 | `TASK-20260528-01` P1 | `from rand_research.integrations import ...` の既存利用を壊さないことが runtime 互換条件。 |
| OBS-004 | black-box runtime 経路が `status=ok` で完走する | flow / state | 主経路、履歴依存 | `AC-20260528-01`、CLI 実行結果 | 共通 writer と分割後 module が実 run artifact / state 更新で壊れていないことを確認する。 |
| OBS-005 | Code-to-gate release gate が findings 0 になる | regression / rule | 静的 gate、差分回帰 | `docs/evaluation.md` AC-14、Code-to-gate 出力 | High 指摘消し込みだけでなく、分割後の residual finding を 0 にする。 |
| OBS-006 | schema compatibility が維持される | data / regression | 同値分割、契約確認 | `report.json`, `memx_journal.json`, `tracker_sync.json`, `state/taskstate.json` | downstream が参照する JSON artifact の `schema_version` と状態更新が維持される必要がある。 |

## リスク

| id | scenario | I | L | modifiers | score | priority | rationale |
|---|---|---:|---:|---|---:|---|---|
| RISK-001 | atomic write 失敗時に既存 state / report が破損する | 5 | 2 | D=2 C=2 X=0 P=2 A=3 | 39 | P2 | 影響は大きいが、異常系テストと `uv run pytest` が対象経路を確認済み。 |
| RISK-002 | cleanup が target parent 外のファイルに触れる | 5 | 1 | D=2 C=1 X=0 P=2 A=3 | 23 | P3 | 境界テストと Code-to-gate findings 0 により、現時点の残余リスクは低い。 |
| RISK-003 | `integrations.py` 分割で既存 import / CLI 経路が壊れる | 4 | 2 | D=1 C=3 X=1 P=0 A=3 | 32 | P3 | CLI black-box 実行と integration tests が通過。公開 import 互換も維持。 |
| RISK-004 | artifact schema が silently drift する | 4 | 2 | D=2 C=2 X=1 P=1 A=2 | 39 | P2 | 今回の schema 確認は最低限。今後 IPO レベルでは JSON schema contract test 化が望ましい。 |
| RISK-005 | Code-to-gate 除外条件が広すぎて重要 finding を見落とす | 4 | 2 | D=2 C=2 X=0 P=0 A=1 | 39 | P2 | 除外は runtime 生成物と egg-info に限定。現行 gate としては許容。 |

## 優先度

| priority | items | 判定 |
|---|---|---|
| P0 | blocker / data loss / irreversible operation | 該当なし。P0 fail なし。 |
| P1 | release gate / runtime black-box / schema compatibility | 全件 pass。 |
| P2 | contract test 強化 / fsync durability | follow-up 候補。今回 release gate の blocker ではない。 |
| P3 | cleanup polish / documentation refinement | 任意。 |

## 手動テストケース

| tc_id | priority | title | preconditions | steps | expected | oracle | trace_to | result | minutes |
|---|---|---|---|---|---|---|---|---|---:|
| TC-001 | P1 | 自動テスト一式が通る | `research-runtime` に移動済み | `uv run pytest` | すべて pass | specified: `AC-20260528-01` | OBS-001, OBS-002, OBS-003 | pass: 44 passed | 3 |
| TC-002 | P1 | heartbeat dry-run が black-box 応答を返す | runtime dependencies available | `uv run python -m rand_research.cli heartbeat --dry-run --max-items 2` | preset / timezone / timestamp を返す | specified: `AC-20260528-01` | OBS-003, OBS-004 | pass: `preset=paper_arxiv_ai_recent`, `timezone=Asia/Tokyo` | 1 |
| TC-003 | P1 | offline eval が artifact と state を生成する | fixture preset available | `uv run python -m rand_research.cli run-once --preset kano_requirements_offline_eval --max-items 3` | `status=ok`、run artifact 作成、taskstate 更新 | specified: `AC-20260528-01` | OBS-004, OBS-006 | pass: run_id `20260528-134343-e616c0bb`, `status=ok` | 1 |
| TC-004 | P1 | Code-to-gate release gate が findings 0 になる | code-to-gate CLI available | `node ...\\code-to-gate\\dist\\cli.js analyze ...` | Critical / High / Medium / Low がすべて 0 | specified: `docs/evaluation.md` AC-14 | OBS-005 | pass: `findings=0`, `risks=0` | 1 |
| TC-005 | P2 | schema compatibility を spot check する | TC-003 の run_id がある | generated JSON と `state/taskstate.json` の `schema_version` / latest run を確認 | `schema_version=1.0`、latest run が TC-003 と一致 | derived: artifact contract | OBS-006 | pass: `taskstate latest=20260528-134343-e616c0bb` | 2 |

## 工数

- prep: 10 分
- execution: 8 分
- evidence: 10 分
- retry buffer: 10 分
- total: 38 分

## Gate

- profile: standard
- decision: go
- reasons:
  - `uv run pytest`: 44 passed
  - heartbeat dry-run: `preset=paper_arxiv_ai_recent`, `timezone=Asia/Tokyo`
  - `kano_requirements_offline_eval`: run_id `20260528-134343-e616c0bb`, `status=ok`
  - Code-to-gate: Critical 0 / High 0 / Medium 0 / Low 0 / Suppressed 0
  - generated artifacts と `state/taskstate.json` は `schema_version=1.0`
- blocking_risks:
  - なし
- waivers:
  - なし

## Go/No-Go Brief

- feature: Code-to-gate hardening for RanD runtime persistence and integration boundary
- decision: go
- top risks:
  - artifact schema drift は今後 JSON schema contract test 化が望ましい。
  - crash durability の厳密化が必要な場合は `fsync` を follow-up で扱う。
- evidence:
  - `uv run pytest`: 44 passed
  - `uv run python -m rand_research.cli heartbeat --dry-run --max-items 2`: pass
  - `uv run python -m rand_research.cli run-once --preset kano_requirements_offline_eval --max-items 3`: pass
  - Code-to-gate run_id `ctg-202605281352`: findings 0 / risks 0
- residual risk:
  - low to medium。release blocker はなし。
- required follow-up:
  - IPO hardening の次段では schema contract test、Evidence chain、replay / idempotency 検収を別 Task Seed 化する。
