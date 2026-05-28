---
bb_acceptance_id: BB-20260528-02
task_id: TASK-20260528-02
acceptance_id: AC-20260528-02
intent_id: INT-KANO-EVAL-001
owner: rand
status: go
profile: standard
executed_at: 2026-05-28
tooling:
  - manual-bb-test-harness
  - code-to-gate v1.3.0
---

# KanoMode Eval hardening release acceptance

## Intake Status

- status: ok
- scope:
  - audit overall verdict の `no_go` 伝播
  - discovery promotion gate の強化
  - discovery / audit golden fixture
  - CLI black-box Eval
  - Code-to-gate release gate
- assumptions:
  - fixture ベースの discovery / audit eval を release acceptance の正本にする。
  - live web evidence、LLM provider 分類精度、外部 tracker 実送信は今回の release gate 対象外。
- blockers:
  - なし

## 根拠付き観点

| id | title | view | techniques | source | rationale |
|---|---|---|---|---|---|
| OBS-001 | `no_go` 要件が audit overall を止める | rule / state | デシジョンテーブル、状態遷移 | `TASK-20260528-02` P0、`test_kano.py` | 要件監査で 1 件でも No-Go があれば release 判断を Go にしてはいけない。 |
| OBS-002 | runtime 実行成功と要件監査 verdict が分離される | flow / rule | 主経路、デシジョン | `AC-20260528-02` | `status=ok` は CLI 完走であり、要件監査 Go ではない。 |
| OBS-003 | discovery promotion gate が危険な昇格を止める | data / rule | 同値分割、境界値、負例 | `_promotable()`, `test_kano.py` | 低 confidence、`questionable`、証拠 tier 不足を packet 昇格させない。 |
| OBS-004 | attractive が hard gate 化されない | rule / regression | デシジョン、回帰 | `test_attractive_candidate_remains_soft_experiment_gate` | attractive を must_be 扱いすると gate overreach になる。 |
| OBS-005 | golden fixture が eval 期待値を固定する | regression | golden test | `kano_expected_packet.json`, `audit_expected_summary.json` | smoke ではなく、昇格件数と verdict distribution の回帰を検出する。 |
| OBS-006 | Code-to-gate が release blocker を出していない | regression / static gate | 静的解析 | `ctg-202605281422` | Critical/High/Medium/Low finding が残っていないことを release gate として確認する。 |

## リスク

| id | scenario | I | L | modifiers | score | priority | rationale |
|---|---|---:|---:|---|---:|---|---|
| RISK-001 | No-Go 要件があるのに overall が Go/Conditional Go になる | 5 | 1 | D=1 C=2 X=0 P=0 A=3 | 23 | P3 | 修正後の CLI audit eval で `overall_assessment=no_go` を確認済み。 |
| RISK-002 | 低品質な候補が requirements packet に昇格する | 5 | 2 | D=2 C=2 X=0 P=1 A=3 | 37 | P2 | promotion gate と unit tests で低 confidence / questionable / tier 不足を拒否。 |
| RISK-003 | golden fixture が浅く、細かい drift を見逃す | 3 | 1 | D=1 C=2 X=0 P=0 A=1 | 20 | P3 | requirement_id、candidate_id、priority、gate_policy、confidence、statement、evidence refs、rejection reasons まで検証するよう強化済み。 |
| RISK-004 | live evidence / LLM 分類では fixture と違う挙動になる | 4 | 3 | D=2 C=2 X=2 P=0 A=1 | 48 | P2 | 今回の Go は fixture-based release gate に限定する。live pilot は別 Task Seed で扱うため、この release gate の blocker ではない。 |

## 優先度

| priority | items | 判定 |
|---|---|---|
| P0 | No-Go 伝播、promotion gate | pass |
| P1 | golden fixture、CLI black-box、Code-to-gate | pass |
| P2 | live pilot eval、parallel state write hardening | follow-up |

## 手動テストケース

| tc_id | priority | title | preconditions | steps | expected | oracle | trace_to | result | minutes |
|---|---|---|---|---|---|---|---|---|---:|
| TC-001 | P1 | unit / golden tests が通る | `research-runtime` に移動 | `uv run pytest` | 全件 pass | specified: `AC-20260528-02` | OBS-001..OBS-005 | pass: 58 passed | 3 |
| TC-002 | P1 | discovery eval が promotion gate を反映する | fixture available | `uv run python -m rand_research.cli run-once --preset kano_requirements_offline_eval --max-items 5` | `status=ok`、promoted 1 件、attractive は未昇格 | specified/golden | OBS-002, OBS-003, OBS-004 | pass: run_id `20260528-141817-a36d15a4` | 1 |
| TC-003 | P1 | audit eval が No-Go を overall に伝播する | fixture available | `uv run python -m rand_research.cli run-once --preset kano_requirements_audit --max-items 5` | `status=ok`、`overall_assessment=no_go`、go=1/conditional=1/no_go=1 | specified/golden | OBS-001, OBS-002, OBS-005 | pass: run_id `20260528-141925-a05fc0f1` | 1 |
| TC-004 | P1 | Code-to-gate が release blocker を出さない | code-to-gate CLI available | `node ... code-to-gate ... --out C:\tmp\rand-code-to-gate-kano ...` | Critical / High / Medium / Low が 0 | specified: AC-14 | OBS-006 | pass: `ctg-202605281422`, findings 0 | 1 |

## 工数

- prep: 8 分
- execution: 6 分
- evidence: 8 分
- retry buffer: 8 分
- total: 30 分

## Gate

- profile: standard
- decision: go
- reasons:
  - `uv run pytest`: 58 passed
  - discovery CLI: `status=ok`, promoted 1 件、低 confidence attractive は未昇格
  - audit CLI: `status=ok`, `overall_assessment=no_go`, `go=1`, `conditional_go=1`, `no_go=1`
  - discovery golden: promoted `REQ-001` / `KC-001` の ID drift を検出できる粒度まで強化済み
  - Code-to-gate `ctg-202605281422`: Critical 0 / High 0 / Medium 0 / Low 0 / Suppressed 0
- blocking_risks:
  - なし
- waivers:
  - なし

## Go/No-Go Brief

- feature: KanoMode Eval hardening
- decision: go
- top risks:
  - live evidence / LLM 分類の品質保証は今回の release gate 対象外。
  - 連続 CLI 実行は検収済み。並列 CLI state write は別途 hardening 対象。
- evidence:
  - `uv run pytest`: 58 passed
  - discovery run_id `20260528-141817-a36d15a4`: `status=ok`, promoted `REQ-001` / `KC-001`, low-confidence attractive `KC-002` rejected
  - audit run_id `20260528-141925-a05fc0f1`: `status=ok`, `overall_assessment=no_go`
  - Code-to-gate run_id `ctg-202605281422`: findings 0 / risks 0
- residual risk:
  - fixture-based release gate は Go。
  - live evidence を使う社内本導入は追加 pilot gate で判定する。
- required follow-up:
  - live evidence pilot Eval、parallel state write hardening、requirements packet の downstream adapter 検収を別 Task Seed 化する。
