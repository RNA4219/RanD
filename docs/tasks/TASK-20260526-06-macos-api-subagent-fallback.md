---
task_id: TASK-20260526-06
status: done
source: docs/requirements.md#42-runtime--state
owner: rand
---

# Mac対応とAPI/subagent fallback

## Objective

RanD の runtime を macOS / Linux でも起動できるようにし、Insight / Gate の実行を外部 API 優先に変更する。API が失敗した場合は、設定済みサブエージェントコマンドへ同じ request payload を渡して処理を継続する。

## Requirements

- macOS / Linux 向けに `bash` 入口を追加する。
- Windows 既存入口は維持する。
- installer は既存 PowerShell 実体を `pwsh` で再利用する。
- Insight / Gate は `RAND_INSIGHT_API_URL`, `RAND_GATE_API_URL` があれば API を優先する。
- API 失敗時は `RAND_INSIGHT_SUBAGENT_CMD`, `RAND_GATE_SUBAGENT_CMD` を stdin JSON で呼ぶ。
- API / subagent / peer repo import が使えなくても deterministic fallback で artifact 契約を満たす。

## Acceptance

- `docs/requirements.md`, `docs/specification.md`, `docs/evaluation.md` に同じ要求が反映されている。
- `run-research-once.sh`, `run-research-schedule.sh`, `install-r-and-d-agent.sh`, `research-runtime/scripts/*.sh` が存在する。
- `uv run python -m unittest discover tests` が通る。
- API 優先と subagent fallback の unit test が存在する。

## Commands

```powershell
cd research-runtime
uv run python -m unittest discover tests
```

```bash
cd research-runtime
./scripts/env-check.sh
./scripts/run-once.sh paper_arxiv_ai_recent 2
```
