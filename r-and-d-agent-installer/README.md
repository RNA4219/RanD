# R&D Agent Installer

`r-and-d-agent-installer` は、RanD アーキテクチャの導入層です。必要な OSS を pinned commit で `.installed/` 配下へ展開し、他人の環境でも再現しやすい導入入口を提供します。

## 何をするか

- manifest で導入対象 OSS と pinned commit を管理する
- `CODEX_DEV_ROOT` を正本に、ローカル repo の解決規則を共通化する
- override JSON や repo 個別環境変数でローカルパス差し替えを許可する
- `local`, `auto`, `remote` の 3 モードで導入元を選ぶ
- 導入先を `.installed/` に閉じ込め、Git 管理対象から外す

## path 解決規則

各 component の local path は manifest に絶対パスを書かず、次の優先順位で解決します。

1. `config/localPathOverrides.json`
2. `.installed/config/localPathOverrides.json`
3. repo 個別環境変数
4. `CODEX_DEV_ROOT + relativePath`
5. `remoteUrl`

`-Mode local` では local path が解決できない component を warning 付きで skip します。`-Mode auto` では local path が使えない component だけ remote clone に fallback します。`-Mode remote` は常に remote clone を使います。

## セットアップ

1. `.env.example` を参考に `.env` を作る
2. 必要なら `config/localPathOverrides.example.json` を `config/localPathOverrides.json` として複製する
3. `./scripts/status.ps1` で解決状況を見る
4. `./scripts/install.ps1` を実行する

例:

```powershell
Set-Location .\r-and-d-agent-installer
Copy-Item .env.example .env
.\scripts\status.ps1
.\scripts\install.ps1 -Mode auto
```

## `.env` 例

- `CODEX_DEV_ROOT=C:\dev\Codex_dev`
- `RAND_LOCAL_PATH_PULSE_KESTRA=C:\alt\pulse-kestra`

詳細は次を参照してください。

- [components.md](docs/components.md)
- [.env.example](.env.example)
- [localPathOverrides.example.json](config/localPathOverrides.example.json)

## ディレクトリ構成

```text
r-and-d-agent-installer/
├─ docs/
├─ manifests/
├─ scripts/
├─ config/
├─ .env.example
└─ .gitignore
```

導入後は次が生成されます。

```text
.installed/
├─ repos/
├─ state/
├─ logs/
└─ config/
```

## 対象レイヤ

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
