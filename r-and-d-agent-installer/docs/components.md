# Components Map

`docs/architecture.md` を、導入対象コンポーネントへ写像した一覧です。

| Layer | Component | Install Mode | Local Resolution | Notes |
| --- | --- | --- | --- | --- |
| Trigger / Entry | `pulse-kestra` | required | `CODEX_DEV_ROOT` / override / env | Misskey / webhook / cron 入口 |
| Trigger / Entry | `kestra` | required | remote-first | オーケストレータ本体 |
| Guard | `llm-guard` | required | remote-first | 入出力ガード層 |
| Research | `open_deep_research` | required | remote-first | 探索レイヤ |
| Insight | `insight-agent` | required | `CODEX_DEV_ROOT` / override / env | 洞察抽出 |
| Experiment Gate | `experiment-gate` | required | `CODEX_DEV_ROOT` / override / env | Go / Hold / No-Go 判定 |
| Planning | `Roadmap-Design-Skill` | required | `CODEX_DEV_ROOT` / override / env | planning-ready 入力をロードマップ化 |
| State | `agent-taskstate` | required | `CODEX_DEV_ROOT` / override / env | 実行状態の正本 |
| Knowledge | `memx-resolver` | required | `CODEX_DEV_ROOT` / override / env | 長期知識と resolver |
| External Sync | `tracker-bridge-materials` | required | `CODEX_DEV_ROOT` / override / env | GitHub / Jira / Linear / Backlog 連携 |
| Policy | `strategy-guided-policy-prompt` | required | remote-first | 横断ポリシー層 |
| Implementation Handoff | `ai-product-requirement-document` | optional | `CODEX_DEV_ROOT` / override / env | 交換可能な出口層 |
| Implementation Handoff | `workflow-cookbook` | optional | `CODEX_DEV_ROOT` / override / env | 交換可能な出口層 |

## local path の解決規則

installer は `localPath` の絶対パスを manifest に持ちません。各 component は `pathKey`, `relativePath`, `envVar` を持ち、次の順で local path を解決します。

1. `config/localPathOverrides.json`
2. `.installed/config/localPathOverrides.json`
3. component ごとの環境変数
4. `CODEX_DEV_ROOT + relativePath`
5. remote clone

この順にすることで、manifest には pinned commit と relativePath だけを残しつつ、各利用者の作業環境差を吸収できます。

## 導入後の推奨確認

1. `./scripts/status.ps1` で `ResolvedLocalPath` と `LocalResolution` を確認する
2. `./scripts/install.ps1 -Mode auto` で `.installed/repos/` を構成する
3. 各 repo の README に従って個別セットアップを行う
4. 最小 E2E として `pulse-kestra -> Kestra -> research -> insight -> gate -> state/sync` の流れを確認する
