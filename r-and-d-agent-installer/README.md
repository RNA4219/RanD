# R&D Agent Installer

`r-and-d-agent-installer` は、RanD アーキテクチャの導入層です。必要な OSS を pinned commit で `.installed/` 配下へ展開し、公開リポジトリとして再現しやすい導入入口を提供します。

## 何を install するか

- Trigger / Entry: `pulse-kestra`, `kestra`
- Guard: `llm-guard`
- Research: `open_deep_research`
- Insight: `insight-agent`
- Experiment Gate: `experiment-gate`
- Planning: `Roadmap-Design-Skill`
- State: `agent-taskstate`
- Knowledge: `memx-resolver`
- External Sync: `tracker-bridge-materials`
- Policy: `strategy-guided-policy-prompt`
- Implementation Handoff: `ai-product-requirement-document`, `workflow-cookbook`

## pinned commit の意味

installer は各 component を `pinnedCommit` へ checkout します。これにより、GitHub 側や `CODEX_DEV_ROOT` 側の最新更新に引きずられず、同じ版を再現できます。

## path schema

manifest は `localPath` の絶対パスを持ちません。各 component は次の key で local path を解決します。

- `pathKey`
- `relativePath`
- `envVar`
- `remoteUrl`
- `installSubdir`
- `pinnedCommit`

解決優先順位は次です。

1. `config/localPathOverrides.json`
2. `.installed/config/localPathOverrides.json`
3. repo 個別環境変数
4. `CODEX_DEV_ROOT + relativePath`
5. `remoteUrl`

## 公開設定 / example / local override

- 公開デフォルト
  - `manifests/components.json`
  - `scripts/*.ps1`
- example
  - `.env.example`
  - `config/localPathOverrides.example.json`
- local override
  - `.env`
  - `config/localPathOverrides.json`
  - `.installed/config/localPathOverrides.json`

## クイックスタート

```powershell
Set-Location .\r-and-d-agent-installer
Copy-Item .env.example .env
.\scripts\status.ps1
.\scripts\install.ps1 -Mode auto
```

## local override の置き場

- `.env`
  - `CODEX_DEV_ROOT` や repo 個別 `RAND_LOCAL_PATH_*`
- `config/localPathOverrides.json`
  - 公開 repo を汚さずに repo ごとの path を差し替える
- `.installed/config/localPathOverrides.json`
  - 実導入先ごとの override を持ちたい場合に使用

詳細は次を参照してください。

- [components.md](docs/components.md)
- [.env.example](.env.example)
- [localPathOverrides.example.json](config/localPathOverrides.example.json)
