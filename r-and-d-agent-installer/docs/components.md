# Components Map

`C:\Users\ryo-n\Codex_dev\RanD\docs\architecture.md` を、導入対象コンポーネントへ写像した一覧です。

| Layer | Component | Install Mode | Source Priority | Notes |
|---|---|---|---|---|
| Trigger / Entry | `pulse-kestra` | required | local-first | Misskey / webhook / cron 入口 |
| Trigger / Entry | `kestra` | required | remote-first | オーケストレータ本体 |
| Guard | `llm-guard` | required | remote-first | 入出力ガード層 |
| Research | `open_deep_research` | required | remote-first | 探索レイヤ |
| Insight | `insight-agent` | required | local-first | 洞察抽出 |
| Experiment Gate | `experiment-gate` | required | local-first | Go / Hold / No-Go 判定 |
| Planning | `Roadmap-Design-Skill` | required | local-first | planning-ready 入力をロードマップ化 |
| State | `agent-taskstate` | required | local-first | 実行状態の正本 |
| Knowledge | `memx-resolver` | required | local-first | 長期知識と resolver |
| External Sync | `tracker-bridge-materials` | required | local-first | GitHub / Jira / Linear / Backlog 連携 |
| Policy | `strategy-guided-policy-prompt` | required | remote-first | 横断ポリシー層 |
| Implementation Handoff | `ai-product-requirement-document` | optional | local-first | 交換可能な出口層 |
| Implementation Handoff | `workflow-cookbook` | optional | local-first | 交換可能な出口層 |

## 設計上の扱い

- `required`: 最小 E2E を通すために導入したいコンポーネント
- `optional`: architecture.md 内で将来差し替え前提とされているコンポーネント
- `local-first`: `Codex_dev` に同名 repo がある場合は、その repo を clone 元に使う
- `remote-first`: ローカルに無い前提で clone しやすいコンポーネント
- 実際の導入先はすべて `manifests/components.json` の `pinnedCommit` に固定される

## 導入後の推奨確認

1. `.\scripts\status.ps1` で local / remote の解決見込みを確認する
2. `.\scripts\install.ps1` で `.installed/repos/` を構成する
3. 各 repo の README に従って個別セットアップを行う
4. 最小 E2E として `pulse-kestra -> research -> insight -> gate -> roadmap -> agent-taskstate` の流れを確認する
