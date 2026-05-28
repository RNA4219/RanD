---
task_id: TASK-20260528-02
intent_id: INT-KANO-EVAL-001
status: done
source: docs/acceptance/BB-20260528-01-code-to-gate-hardening.md
owner: rand
last_reviewed_at: 2026-05-28
next_review_due: 2026-06-04
---

# KanoMode Eval hardening

## Objective

KanoMode の offline eval / audit eval を、単なる artifact 生成 smoke から、社内導入判断に使える Requirement Definition Gate へ引き上げる。

## Background

2026-05-28 の Code-to-gate hardening 検収では、`kano_requirements_offline_eval` と `kano_requirements_audit` は `status=ok` で完走することを確認した。

ただし、導入判断に使う Eval としては次の懸念が残る。

- `kano_requirements_audit` の fixture に `no_go` 要件が含まれていても、`gate_summary.overall_assessment` が `conditional_go` になり得る。
- discovery 側の `_promotable()` は `confidence`, `bias_note`, `kill_condition` の truthy 判定に留まり、confidence 閾値、証拠 tier、`questionable` 除外、Kano type と gate policy の整合を十分に検証していない。
- 現行テストは artifact contract / smoke に寄っており、「分類・昇格・監査 verdict が壊れたら検出できる golden Eval」になっていない。
- CLI black-box では `status=ok` と「監査が Go か No-Go か」が分離されていない。

本 Task は、KanoMode を限定パイロット導入に進める前に、Eval 自体が危険な要求昇格や誤った Go 判定を止められる状態にする。

## Scope

- In:
  - `research-runtime/src/rand_research/kano.py`
  - `research-runtime/tests/test_kano.py`
  - `research-runtime/tests/fixtures/kano_evidence.json`
  - `research-runtime/tests/fixtures/audit_evidence.json`
  - 新規 golden fixture
  - `docs/evaluation.md`
  - `RUNBOOK.md`
  - `docs/acceptance/AC-20260528-02.md`
- Out:
  - live web search 必須化
  - LLM provider による Kano 分類推論の本格実装
  - manual-bb-test-harness / code-to-gate 本体の変更
  - Kestra flow の本格改修
  - Misskey / tracker 実送信

## Requirements

### P0: audit overall verdict の no_go 伝播を修正する

- `requirements_audit_packet.gate_summary.overall_assessment` は、`no_go` 要件が 1 件でもあれば `no_go` にする。
- `no_go` が 0 かつ `conditional_go` が 1 件以上なら `conditional_go` にする。
- 全件 `go` の場合のみ `go` にする。
- `overall_reason` は verdict と矛盾しない文言にする。
- `test_gate_summary_counts_verdicts` などで `no_go` 伝播を明示的に検証する。

### P0: discovery 昇格 gate を強化する

`requirements_packet.requirements` への昇格条件を次のように固定する。

- `confidence >= 0.7`
- `bias_note` が非空
- `kill_condition` が非空
- evidence が 1 件以上
- evidence に `source_tier in ("primary", "user_signal")` が 1 件以上
- `kano_type == "questionable"` は昇格禁止
- `kano_type == "attractive"` は `priority=P2` かつ `gate_policy=soft_experiment_gate` のまま維持し、`hard_gate` にしない

### P1: golden fixture を追加する

- `tests/fixtures/kano_expected_packet.json` を追加し、discovery Eval の期待値を固定する。
  - promoted requirements 件数
  - `requirement_id`
  - `priority`
  - `gate_policy`
  - `evidence_refs`
  - 非昇格 candidate の理由
- `tests/fixtures/audit_expected_summary.json` を追加し、audit Eval の期待値を固定する。
  - verdict distribution
  - `overall_assessment`
  - `no_go` requirement IDs
  - `conditional_go` requirement IDs

### P1: CLI black-box Eval を acceptance 化する

- `kano_requirements_offline_eval` は `status=ok` と artifact 生成だけでなく、golden 期待値と一致することを検証する。
- `kano_requirements_audit` は `status=ok` で完走しても、fixture に `no_go` が含まれる場合は `overall_assessment=no_go` を返すことを検証する。
- 「実行成功」と「要件監査 Go」は別概念として docs / acceptance に明記する。

### P1: manual BB / Code-to-gate 再検収

- 改修後に次を再実行する。
  - `uv run pytest`
  - `uv run python -m rand_research.cli run-once --preset kano_requirements_offline_eval --max-items 5`
  - `uv run python -m rand_research.cli run-once --preset kano_requirements_audit --max-items 5`
  - Code-to-gate analyze
- manual-bb-test-harness 形式で Go/No-Go brief を更新する。

## Affected Paths

- `research-runtime/src/rand_research/kano.py`
- `research-runtime/tests/test_kano.py`
- `research-runtime/tests/fixtures/kano_evidence.json`
- `research-runtime/tests/fixtures/audit_evidence.json`
- `research-runtime/tests/fixtures/kano_expected_packet.json`
- `research-runtime/tests/fixtures/audit_expected_summary.json`
- `docs/evaluation.md`
- `RUNBOOK.md`
- `docs/acceptance/AC-20260528-02.md`
- `docs/acceptance/BB-20260528-02-kano-eval-hardening.md`

## Acceptance Criteria

- `uv run pytest` が通る。
- audit fixture に `no_go` が 1 件以上ある場合、`requirements_audit_packet.gate_summary.overall_assessment` が `no_go` になる。
- discovery fixture の低 confidence / `questionable` / low evidence tier 候補が `requirements_packet` に昇格しない。
- attractive 候補が `P2` / `soft_experiment_gate` として残り、hard gate にならない。
- golden fixture によって discovery / audit の期待値が regression test される。
- CLI black-box eval で `status=ok` と gate verdict が別々に確認される。
- Code-to-gate 再実行で Critical / High / Medium / Low effective finding が 0 になる。
- `docs/acceptance/AC-20260528-02.md` に検証コマンドと結果が記録される。

## Local Commands

```powershell
cd C:\Users\ryo-n\Codex_dev\RanD\research-runtime
uv run pytest
uv run python -m rand_research.cli run-once --preset kano_requirements_offline_eval --max-items 5
uv run python -m rand_research.cli run-once --preset kano_requirements_audit --max-items 5
```

```powershell
cd C:\Users\ryo-n\Codex_dev\RanD
node C:\Users\ryo-n\Codex_dev\code-to-gate\dist\cli.js analyze C:\Users\ryo-n\Codex_dev\RanD --emit all --out C:\tmp\rand-code-to-gate-clean --llm-provider deterministic --cache force --ignore research-runtime/runs,research-runtime/state,research-runtime/.pytest_cache,research-runtime/src/rand_research_runtime.egg-info
```

## Implementation Order

1. `gate_summary.overall_assessment` の `no_go` 伝播バグを修正し、unit test を追加する。
2. `_promotable()` を明示的な promotion gate に置き換え、低 confidence / `questionable` / 証拠不足テストを追加する。
3. discovery / audit golden fixture を追加し、既存 fixture と expected output の差分を検証する。
4. CLI black-box eval の artifact を読み、`status` と gate verdict を別々に検証する。
5. `uv run pytest`、offline eval、audit eval、Code-to-gate を再実行する。
6. `AC-20260528-02` と manual BB acceptance を検証結果で更新する。

## Tests

### Unit

- `test_gate_summary_no_go_overrides_conditional`
- `test_promotable_rejects_low_confidence_candidate`
- `test_promotable_rejects_questionable_candidate`
- `test_promotable_rejects_unknown_tier_only_candidate`
- `test_attractive_candidate_remains_soft_experiment_gate`

### Golden

- `test_discovery_matches_expected_packet_golden`
- `test_audit_matches_expected_summary_golden`

### CLI Black-box

- `kano_requirements_offline_eval` run artifact が golden 期待値と一致する。
- `kano_requirements_audit` run artifact が `overall_assessment=no_go` を返す。

## Notes

- 現状の KanoMode Eval は smoke / contract eval としては有効だが、社内導入判断の gate としては不足している。
- 本 Task の完了条件は「KanoMode が常に Go になる」ことではなく、「危険な要求昇格や No-Go 条件を Eval が止められる」ことである。
- `status=ok` は runtime 実行成功を意味し、`overall_assessment=go` を意味しない。この分離を docs / acceptance の正本にする。
- 2026-05-28 検収では `uv run pytest` 58 passed、discovery run_id `20260528-141817-a36d15a4`、audit run_id `20260528-141925-a05fc0f1`、Code-to-gate run_id `ctg-202605281422` により fixture-based KanoMode Eval release gate を Go とした。
