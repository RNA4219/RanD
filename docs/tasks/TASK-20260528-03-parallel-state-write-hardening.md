---
task_id: TASK-20260528-03
intent_id: INT-STATE-001
status: planned
source: RUNBOOK.md#5.3
owner: rand
last_reviewed_at: 2026-05-28
next_review_due: 2026-06-04
---

# Parallel state write hardening

## Objective

CLI 並列実行時の state file 書き込み競合を回避し、transient `state_write_failed` を排除する。

## Background

2026-05-28 14:18:17 UTC に `task-20260528-141817-44b2dc68` (kano_requirements_audit) で `state_write_failed` が発生した。原因は offline_eval / audit の同時起動による `taskstate.json` 書き込み競合である。

atomic write による file corruption 回避は TASK-20260528-01 で実装済みだが、並列実行時の concurrent write は未対応。

## Scope

- In:
  - `research-runtime/src/rand_research/state_store.py`
  - `research-runtime/src/rand_research/cli.py`
- Out:
  - Kestra flow の本格改修
  - distributed lock の導入

## Requirements

### P1: file lock の追加

- `taskstate.json` 書き込み前に file lock を取得する
- lock 取得失敗時は retry または skip する
- Windows / macOS / Linux で動作する

### P2: CLI serial execution mode

- `--serial` オプションで並列実行を禁止する
- preset 同時起動時は警告を出す

## Acceptance Criteria

- 並列実行で `state_write_failed` が発生しない
- 既存単独実行が変わらない
- pytest が通る

## Priority

P2 (non-blocking): 現状の transient failure は単独再実行で回復可能であるため blocker ではない。

## Notes

- 現状の atomic write は同一 process 内の concurrent write を防ぐが、multi-process は未対応
- file lock は platform-dependent であるため、cross-platform 対応が必要