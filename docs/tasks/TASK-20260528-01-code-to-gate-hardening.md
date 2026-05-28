---
task_id: TASK-20260528-01
intent_id: INT-CTG-001
status: done
source: C:/tmp/rand-code-to-gate-clean/analysis-report.md
owner: rand
last_reviewed_at: 2026-05-28
next_review_due: 2026-06-04
---

# Code-to-gate 指摘対応と runtime hardening

## Objective

Code-to-gate の静的診断レポートを根拠に、RanD runtime の永続化処理と integration 境界を IPO クラスの保守性・検証性へ引き上げる。

## Background

2026-05-28 に `code-to-gate v1.3.0` で RanD を解析した。

- 実行コマンド:
  - `node C:\Users\ryo-n\Codex_dev\code-to-gate\dist\cli.js analyze C:\Users\ryo-n\Codex_dev\RanD --emit all --out C:\tmp\rand-code-to-gate-clean --llm-provider deterministic --cache force --ignore research-runtime/runs,research-runtime/state,research-runtime/.pytest_cache,research-runtime/src/rand_research_runtime.egg-info`
- レポート:
  - `C:\tmp\rand-code-to-gate-clean\analysis-report.md`
- 結果:
  - Critical: 0
  - High: 2
  - Medium: 1

Code-to-gate findings:

- `finding-UNSAFE_DELETE-000`
  - 対象: `research-runtime/src/rand_research/integrations.py`
  - 行: 565-571
  - 実体: atomic write の失敗時 cleanup
- `finding-UNSAFE_DELETE-001`
  - 対象: `research-runtime/src/rand_research/state_store.py`
  - 行: 38-44
  - 実体: atomic write の失敗時 cleanup
- `finding-LARGE_MODULE-002`
  - 対象: `research-runtime/src/rand_research/integrations.py`
  - 実体: 602 lines の責務混在

## Scope

- In:
  - `research-runtime/src/rand_research/io_utils.py`
  - `research-runtime/src/rand_research/state_store.py`
  - `research-runtime/src/rand_research/integrations.py`
  - 必要に応じた integration 分割先 module
  - `research-runtime/tests/`
  - `docs/evaluation.md`
  - `RUNBOOK.md`
- Out:
  - Kestra flow の本格改修
  - Misskey / tracker への実送信実装
  - LLM provider の仕様変更
  - 既存 CLI / JSON artifact の破壊的変更

## Requirements

### P0: atomic write を安全な共通境界へ集約する

- `integrations.py` と `state_store.py` に重複している `_atomic_write` を共通 module へ移す。
- temp file は必ず target parent 配下に作成する。
- cleanup は自分で作成した temp file のみに限定する。
- cleanup 前に `resolve()` ベースで target parent 配下であることを検証する。
- 失敗時も既存 target file を壊さない。
- public behavior は維持する。

### P0: Code-to-gate High 指摘に対するテストを追加する

- 正常系:
  - atomic write が target file を期待内容で置換する。
- 異常系:
  - 書き込み途中の例外で target file が保持される。
  - cleanup 対象が target parent 外なら削除されない。
- 統合:
  - `save_taskstate()` が共通 atomic write を通る。
  - `write_memx_journal()` / `write_tracker_sync()` が共通 atomic write を通る。

### P1: `integrations.py` の責務を分割する

- 分割候補:
  - `env_loader.py`: peer `.env` 読込、provider selection、timeout stretch
  - `llm_bridge.py`: external API / subagent fallback
  - `insight_bridge.py`: Insight payload と run
  - `gate_bridge.py`: Gate payload と run
  - `sync_writers.py`: memx / tracker JSON 永続化
- 既存 import 互換を維持する。
  - `from rand_research.integrations import run_insight`
  - `run_gate`
  - `write_memx_journal`
  - `write_tracker_sync`
  - `check_dependencies`
- 1 回の PR で大きくしすぎない。P0 と P1 は分けてもよい。

### P1: release gate に Code-to-gate を追加する

- Runbook に Code-to-gate 実行手順を追加する。
- 除外対象を明記する。
  - `research-runtime/runs`
  - `research-runtime/state`
  - `research-runtime/.pytest_cache`
  - `research-runtime/src/rand_research_runtime.egg-info`
- 完了時に Code-to-gate 再実行結果を acceptance に記録する。

## Affected Paths

- `research-runtime/src/rand_research/integrations.py`
- `research-runtime/src/rand_research/state_store.py`
- `research-runtime/src/rand_research/io_utils.py`
- `research-runtime/src/rand_research/*_bridge.py`
- `research-runtime/src/rand_research/sync_writers.py`
- `research-runtime/tests/test_state_store.py`
- `research-runtime/tests/test_integrations.py`
- `research-runtime/tests/test_io_utils.py`
- `docs/evaluation.md`
- `RUNBOOK.md`
- `docs/acceptance/AC-20260528-01.md`

## Acceptance Criteria

- `uv run pytest` が通る。
- `uv run python -m rand_research.cli heartbeat --dry-run --max-items 2` が通る。
- `uv run python -m rand_research.cli run-once --preset kano_requirements_offline_eval --max-items 3` が `status: ok` を返す。
- Code-to-gate 再実行で `UNSAFE_DELETE` の effective finding が 0 になる。
- `integrations.py` が 500 lines 未満、または分割未完了の場合は別 Task Seed に follow-up 化されている。
- `report.json`, `memx_journal.json`, `tracker_sync.json`, `state/taskstate.json` の schema compatibility が維持される。
- `docs/acceptance/AC-20260528-01.md` に検証コマンドと結果が記録される。

## Local Commands

```powershell
cd C:\Users\ryo-n\Codex_dev\RanD\research-runtime
uv run pytest
uv run python -m rand_research.cli heartbeat --dry-run --max-items 2
uv run python -m rand_research.cli run-once --preset kano_requirements_offline_eval --max-items 3
```

```powershell
cd C:\Users\ryo-n\Codex_dev\RanD
node C:\Users\ryo-n\Codex_dev\code-to-gate\dist\cli.js analyze C:\Users\ryo-n\Codex_dev\RanD --emit all --out C:\tmp\rand-code-to-gate-clean --llm-provider deterministic --cache force --ignore research-runtime/runs,research-runtime/state,research-runtime/.pytest_cache,research-runtime/src/rand_research_runtime.egg-info
```

## Implementation Order

1. `io_utils.py` と atomic write tests を追加する。
2. `state_store.py` と `integrations.py` を共通 atomic write に切り替える。
3. `uv run pytest` と offline eval を通す。
4. Code-to-gate を再実行し、High finding が消えたか確認する。
5. `integrations.py` の分割を P1 として進める。大きくなる場合は follow-up Task Seed に分ける。
6. `RUNBOOK.md` と `docs/evaluation.md` に release gate 手順を反映する。
7. `docs/acceptance/AC-20260528-01.md` を検証結果で更新する。

## Notes

- 現時点の `UNSAFE_DELETE` は任意削除の直接脆弱性ではなく、atomic write の temp cleanup に対する静的検出である。
- ただし IPO クラスの基盤としては、静的検出を false positive 扱いで残すより、共通化・境界検証・テスト証跡で消し込む。
- 既存 working tree には別件の `pyproject.toml`, `reports.py`, `test_reports.py` 差分がある。実装時は同一 PR に含めるか分離するかを最初に決める。

## Completion Evidence

- `atomic_write_text()` を `research-runtime/src/rand_research/io_utils.py` に追加し、`state_store.py` と sync writer 経由の memx / tracker 永続化を共通化した。
- `integrations.py` から env loading と sync writers を分割し、435 lines まで縮小した。
- `uv run pytest`: 44 passed
- `uv run python -m rand_research.cli heartbeat --dry-run --max-items 2`: `preset=paper_arxiv_ai_recent`, `timezone=Asia/Tokyo`
- `uv run python -m rand_research.cli run-once --preset kano_requirements_offline_eval --max-items 3`: `status=ok`
- Code-to-gate 再実行: Critical 0 / High 0 / Medium 0
