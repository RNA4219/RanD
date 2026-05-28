---
task_id: TASK-20260526-05
intent_id: INT-KANO-001
owner: rand
status: superseded
last_reviewed_at: 2026-05-28
next_review_due: null
superseded_by: TASK-20260528-02
completion_evidence: docs/acceptance/AC-20260528-02.md
---

# Task Seed: KanoMode Audit Mode

## メタデータ

```yaml
task_id: TASK-20260526-05
repo: RanD
base_branch: main
work_branch: codex/kano-audit-mode
priority: P1
langs: [markdown, json, python]
```

## Objective

既存の要件定義を KanoMode で監査し、manual-bb-test-harness と code-to-gate へ渡せる `requirements_audit_packet.json` と Requirement Definition Gate を定義する。

## Scope

- In:
  - `docs/requirements_kano_mode.md`
  - `docs/specification_kano_mode.md`
  - `docs/evaluation.md`
  - `docs/kano_mode_handoff.md`
  - `docs/tasks/*`
  - 将来実装時の `research-runtime` audit preset / fixture / schema
- Out:
  - peer repo の破壊的変更
  - manual-bb-test-harness / code-to-gate 本体の実装変更
  - live web search 必須化

## Requirements

- Behavior:
  - 既存要件定義を audit input として扱えること
  - 要件ごとに Kano 再分類を出せること
  - testability と implementation_alignment を評価できること
  - `go`, `conditional_go`, `no_go` の gate verdict を出せること
  - manual-bb-test-harness と code-to-gate へ渡す観点を分離できること
- I/O Contract:
  - Input: existing requirements document, external evidence, implementation evidence
  - Output: `requirements_audit_packet.json`
- Constraints:
  - 既存の discovery mode を壊さない
  - audit mode は既存要件を正とせず、証跡で再評価する
  - live search は acceptance の必須条件にしない
- Acceptance Criteria:
  - `requirements_audit_packet.json` の artifact 契約が仕様化されている
  - Requirement Definition Gate の判定基準が仕様化されている
  - manual-bb-test-harness / code-to-gate との役割分担が明記されている

## Affected Paths

- `docs/requirements_kano_mode.md`
- `docs/specification_kano_mode.md`
- `docs/evaluation.md`
- `docs/tasks/TASK-20260526-05-kano-audit-mode.md`
- `RUNBOOK.md`

## Local Commands

```powershell
cd research-runtime
uv run python -m unittest discover tests
```

audit mode の実装前は、上記を regression 確認として扱う。

## Deliverables

- `requirements_audit_packet.json` artifact contract
- Requirement Definition Gate 判定基準
- manual-bb-test-harness / code-to-gate 役割分担
- audit mode 用 acceptance criteria

## Plan

### Steps

1. discovery mode と audit mode の責務境界を仕様に固定する
2. `requirements_audit_packet.json` の root / requirement fields を定義する
3. Requirement Definition Gate の `go / conditional_go / no_go` 基準を定義する
4. manual-bb-test-harness / code-to-gate へ渡す field を整理する
5. evaluation に AC-K を追加する
6. 将来実装する場合の fixture / preset / test seed を切る

## Tests

### Outline

- Unit:
  - audit packet schema の必須 field
  - gate verdict の分類
- Integration:
  - 既存要件定義 fixture から audit packet を生成
  - manual-bb-test-harness / code-to-gate 向け field が欠けない
- Regression:
  - discovery mode の offline eval が壊れない

## Task分割

本 Task は次の 3 seed に分割して進行する。

### TASK-20260526-05-1: requirements_audit_packet.json artifact contract

**Objective**: `requirements_audit_packet.json` の root / requirement fields を仕様に固定する。

**Deliverables**:
- specification 6.5節の artifact fields 定義
- evaluation AC-K07 の検収条件明記

**Scope**:
- 文書整備のみ
- sample / fixture 作成はユーザー確認待ち

**Status**: sample artifact作成済み [2026-05-26]
- [docs/examples/requirements_audit_packet.sample.json](../examples/requirements_audit_packet.sample.json)
- 3要件（go/conditional_go/no_go）を含む
- 仕様理解用sample。実装fixtureではない。

### TASK-20260526-05-2: Requirement Definition Gate判定基準

**Objective**: `go / conditional_go / no_go` の判定基準を仕様に固定する。

**Deliverables**:
- specification 7節の判定軸と verdict 条件定義
- evaluation AC-K08 の検収条件明記

**Scope**:
- 文書整備のみ
- gate判定ロジックの実装はユーザー確認待ち

### TASK-20260526-05-3: manual-bb-test-harness / code-to-gate連携

**Objective**: downstream OSS へ渡す field と役割分担を整理する。

**Deliverables**:
- specification 9節の連携表更新
- evaluation AC-K09 の検収条件明記

**Scope**:
- 文書整備のみ
- downstream OSS 側の実装変更は対象外

**進行順序**: 05-1 → 05-2 → 05-3（順次依存）

## Notes

### Rationale

既存要件定義は上流の正本として扱われがちだが、実際には価値根拠、Kano分類、検収可能性、実装整合性がズレることがある。audit mode は、要件定義そのものを品質ゲート対象にする。

### Risks

- audit が重すぎると要件レビューの速度を落とす
- external evidence が弱いと過剰に Conditional Go へ寄る
- implementation_alignment を code-to-gate なしで断定すると誤判定する

### Follow-ups

- audit preset / fixture の追加
- audit packet schema validation
- manual-bb-test-harness への feature_spec 変換
- code-to-gate への intake 変換

### 文書上の次工程

- [../kano_mode_next_steps.md](../kano_mode_next_steps.md) の判断表を正本として、sample から fixture へ昇格するかを決める。
- 実装へ進む場合は、05-1 / 05-2 / 05-3 を実装 PR 単位へ切り直す。
- 実装へ進まない場合は、audit mode を文書ゲートとして運用し、sample artifact をレビュー補助に留める。
