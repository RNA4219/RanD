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
- **[2026-05-26 実装完了]** Discovery mode と Audit mode の実装が完了し、commit済み (`b8db672`)。
- offline eval で `kano.json`、`requirements_packet.json`、`requirements_audit_packet.json` が生成されることを確認済み。
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
