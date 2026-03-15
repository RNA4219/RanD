# Components Map

`docs/architecture.md` を、導入対象コンポーネントへ写像した一覧です。

| Layer | Component | Required | Local Resolution | Notes |
| --- | --- | --- | --- | --- |
| Trigger / Entry | `pulse-kestra` | required | `override -> envVar -> CODEX_DEV_ROOT + relativePath -> remote` | Misskey / webhook / cron 入口 |
| Trigger / Entry | `kestra` | required | `override -> envVar -> CODEX_DEV_ROOT + relativePath -> remote` | オーケストレータ本体 |
| Guard | `llm-guard` | required | `override -> envVar -> CODEX_DEV_ROOT + relativePath -> remote` | 入出力ガード層 |
| Research | `open_deep_research` | required | `override -> envVar -> CODEX_DEV_ROOT + relativePath -> remote` | 探索レイヤ |
| Insight | `insight-agent` | required | `override -> envVar -> CODEX_DEV_ROOT + relativePath -> remote` | 洞察抽出 |
| Experiment Gate | `experiment-gate` | required | `override -> envVar -> CODEX_DEV_ROOT + relativePath -> remote` | Go / Hold / No-Go 判定 |
| Planning | `Roadmap-Design-Skill` | required | `override -> envVar -> CODEX_DEV_ROOT + relativePath -> remote` | planning-ready 入力をロードマップ化 |
| State | `agent-taskstate` | required | `override -> envVar -> CODEX_DEV_ROOT + relativePath -> remote` | 実行状態の正本 |
| Knowledge | `memx-resolver` | required | `override -> envVar -> CODEX_DEV_ROOT + relativePath -> remote` | 長期知識と resolver |
| External Sync | `tracker-bridge-materials` | required | `override -> envVar -> CODEX_DEV_ROOT + relativePath -> remote` | GitHub / Jira / Linear / Backlog 連携 |
| Policy | `strategy-guided-policy-prompt` | required | `override -> envVar -> CODEX_DEV_ROOT + relativePath -> remote` | 横断ポリシー層 |
| Implementation Handoff | `ai-product-requirement-document` | optional | `override -> envVar -> CODEX_DEV_ROOT + relativePath -> remote` | 交換可能な出口層 |
| Implementation Handoff | `workflow-cookbook` | optional | `override -> envVar -> CODEX_DEV_ROOT + relativePath -> remote` | 交換可能な出口層 |

## schema の正本

installer の path schema は次の 3 ファイルを正本とします。

- `manifests/components.json`
- `scripts/Resolve-Components.ps1`
- `docs/components.md`

この 3 つは常に同じ key 名と優先順位を説明する必要があります。

## component schema

各 component は次の key を持つ前提です。

- 必須
  - `name`
  - `layer`
  - `required`
  - `remoteUrl`
  - `installSubdir`
  - `pinnedCommit`
- local path 解決用
  - `pathKey`
  - `relativePath`
  - `envVar`

少なくとも `envVar` または `pathKey + relativePath` のどちらかを持つ必要があります。resolver は必須項目が欠けている component をエラーにします。

## local path の解決規則

各 component は `pathKey`, `relativePath`, `envVar` を持ち、次の順で local path を解決します。

1. `config/localPathOverrides.json`
2. `.installed/config/localPathOverrides.json`
3. component ごとの `envVar`
4. `CODEX_DEV_ROOT + relativePath`
5. `remoteUrl`

## 導入後の推奨確認

1. `./scripts/status.ps1` で `ResolvedLocalPath` と `LocalResolution` を確認する
2. `./scripts/install.ps1 -Mode auto` で `.installed/repos/` を構成する
3. `.env` や `localPathOverrides.json` を使い、個人設定は Git 管理外に置く
4. 最小 E2E として `pulse-kestra -> Kestra -> research -> insight -> gate -> state/sync` の流れを確認する
