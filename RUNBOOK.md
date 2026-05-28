# RanD RUNBOOK

## 1. 目的

RanD の作業再開時に、現在の差分、検証状況、次に読むべき資料を短時間で判断するための運用メモである。

## 2. 現在の優先事項

KanoMode は、まずドキュメント実装として進める。

- 正本要件: [docs/requirements_kano_mode.md](docs/requirements_kano_mode.md)
- 正本仕様: [docs/specification_kano_mode.md](docs/specification_kano_mode.md)
- P0 Task Seed: [docs/tasks/TASK-20260526-01-kano-mode-p0.md](docs/tasks/TASK-20260526-01-kano-mode-p0.md)
- 引継ぎ: [docs/kano_mode_handoff.md](docs/kano_mode_handoff.md)
- エージェント指示: [docs/kano_mode_agent_instruction.md](docs/kano_mode_agent_instruction.md)
- 次工程整理: [docs/kano_mode_next_steps.md](docs/kano_mode_next_steps.md)

## 3. 注意事項

- 現在の working tree には、KanoMode のコード実装に踏み込んだ先行差分が残っている。
- これはユーザーが明示的に依頼した「コード実装」ではなく、次工程の参考証跡として扱う。
- 勝手に revert しない。
- 続きを実装する場合は、ユーザーに「コード実装へ進む」確認を取る。
- 文書だけ整える場合は、`docs/requirements_kano_mode.md`、`docs/tasks/`、`docs/kano_mode_handoff.md` を中心に更新する。
- **[2026-05-26 実装完了]** Discovery mode と Audit mode の実装が完了し、commit済み (`ef89f64`)。
- **[2026-05-26 修正完了]** atomic write対策追加（state file corruption防止）。
- offline eval で `kano.json`、`requirements_packet.json`、`requirements_audit_packet.json` が生成され、`status: ok` になることを確認済み。
- unittest 35 tests OK。

## 4. 検証済みコマンド

2026-05-26 時点で、先行コード差分を含む状態では次が通っている。

```powershell
cd research-runtime
uv run python -m unittest discover tests
```

結果:

```text
Ran 29 tests in 2.622s
OK
```

また、次の offline eval は `status: ok` で `kano.json` と `requirements_packet.json` の artifact path を返すことを確認済み。

```powershell
cd research-runtime
uv run python -m rand_research.cli run-once --preset kano_requirements_offline_eval --max-items 5
```

## 5. 次の再開手順

1. [docs/kano_mode_handoff.md](docs/kano_mode_handoff.md) を読む。
2. `git status --short` で現在の差分を確認する。
3. 文書実装だけ続ける場合は、コード差分には触らず、RUNBOOK / requirements / specification / Task Seed / evaluation の整合だけを更新する。
4. コード実装へ進む場合は、先行差分をレビューしてから正式な P0 実装タスクとして扱う。

## 5.1 Code-to-gate 更新計画

2026-05-28 時点で、Code-to-gate による RanD 静的診断を実施した。

- Task Seed: [docs/tasks/TASK-20260528-01-code-to-gate-hardening.md](docs/tasks/TASK-20260528-01-code-to-gate-hardening.md)
- Acceptance draft: [docs/acceptance/AC-20260528-01.md](docs/acceptance/AC-20260528-01.md)
- 初回レポート: `C:\tmp\rand-code-to-gate-clean\analysis-report.md`
- 結果: Critical 0 / High 2 / Medium 1

再実行:

```powershell
cd C:\Users\ryo-n\Codex_dev\RanD
node C:\Users\ryo-n\Codex_dev\code-to-gate\dist\cli.js analyze C:\Users\ryo-n\Codex_dev\RanD --emit all --out C:\tmp\rand-code-to-gate-clean --llm-provider deterministic --cache force --ignore research-runtime/runs,research-runtime/state,research-runtime/.pytest_cache,research-runtime/src/rand_research_runtime.egg-info
```

実装着手時は、まず `TASK-20260528-01` の P0 を扱う。

1. atomic write を共通 utility に集約する。
2. temp cleanup の境界テストを追加する。
3. `UNSAFE_DELETE` High finding が 0 になることを確認する。
4. `integrations.py` の分割は P1 とし、同一変更で大きくなる場合は follow-up Task Seed に分ける。

## 5.2 KanoMode Eval hardening 計画

2026-05-28 時点で、KanoMode の offline eval / audit eval は `status=ok` で完走するが、社内導入判断に使う Eval gate としては追加 hardening が必要である。

- Task Seed: [docs/tasks/TASK-20260528-02-kano-eval-hardening.md](docs/tasks/TASK-20260528-02-kano-eval-hardening.md)
- Acceptance draft: [docs/acceptance/AC-20260528-02.md](docs/acceptance/AC-20260528-02.md)
- 主な懸念:
  - audit fixture に `no_go` が含まれていても `overall_assessment=conditional_go` になり得る。
  - discovery の昇格条件が smoke / contract test 寄りで、confidence 閾値や証拠 tier を十分に gate していない。
  - `status=ok` と「要件監査が Go であること」が混同されやすい。

実装着手時は、まず `TASK-20260528-02` の P0 を扱う。

1. audit overall verdict で `no_go` を正しく伝播させる。
2. discovery promotion gate を強化する。
3. discovery / audit golden fixture を追加する。
4. CLI black-box eval で `status` と gate verdict を別々に確認する。
5. manual-bb-test-harness と Code-to-gate で再検収する。

## 6. KanoMode 文書正本

KanoMode の文書正本は次の順に読む。

1. [docs/requirements_kano_mode.md](docs/requirements_kano_mode.md)
2. [docs/specification_kano_mode.md](docs/specification_kano_mode.md)
3. [docs/tasks/TASK-20260526-01-kano-mode-p0.md](docs/tasks/TASK-20260526-01-kano-mode-p0.md)
4. [docs/evaluation.md](docs/evaluation.md)
5. [docs/kano_mode_handoff.md](docs/kano_mode_handoff.md)
6. [docs/kano_mode_agent_instruction.md](docs/kano_mode_agent_instruction.md)
7. [docs/kano_mode_next_steps.md](docs/kano_mode_next_steps.md)

KanoMode audit mode を扱う場合は、追加で次を読む。

- [docs/tasks/TASK-20260526-05-kano-audit-mode.md](docs/tasks/TASK-20260526-05-kano-audit-mode.md)

Audit mode の次作業単位:

- [TASK-20260526-05-1](docs/tasks/TASK-20260526-05-kano-audit-mode.md): requirements_audit_packet.json artifact contract
- [TASK-20260526-05-2](docs/tasks/TASK-20260526-05-kano-audit-mode.md): Requirement Definition Gate判定基準
- [TASK-20260526-05-3](docs/tasks/TASK-20260526-05-kano-audit-mode.md): manual-bb-test-harness / code-to-gate連携

Audit mode sample artifact:

- [docs/examples/requirements_audit_packet.sample.json](docs/examples/requirements_audit_packet.sample.json)
  - 仕様理解用sample（go/conditional_go/no_goの3要件例）
  - 実装fixtureではない

仕様変更時は、要件、仕様、検収、Task Seed、引継ぎ資料のうち影響するものを同時に更新する。

## 7. macOS / 外部 API fallback 追記

2026-05-26 時点で、runtime には macOS / Linux 用の shell wrapper と、Insight / Gate の外部 API 優先実行を追加している。

- macOS / Linux runtime 入口: `run-research-once.sh`, `run-research-schedule.sh`, `research-runtime/scripts/*.sh`
- installer の macOS / Linux 入口: `install-r-and-d-agent.sh` (`pwsh` 必須)
- 外部 API: `RAND_INSIGHT_API_URL`, `RAND_GATE_API_URL`
- fallback subagent: `RAND_INSIGHT_SUBAGENT_CMD`, `RAND_GATE_SUBAGENT_CMD`

検証時は `cd research-runtime && uv run python -m unittest discover tests` を正本にする。
