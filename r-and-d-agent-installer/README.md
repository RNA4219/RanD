# R&D Agent Installer

`docs/architecture.md` のレイヤ構成を、そのまま導入可能な形へ落とし込むためのインストール用リポジトリです。

このリポジトリ自体は軽量な制御面だけを持ち、実体の OSS 群は `.installed/` 配下へ展開します。  
`.installed/` は `.gitignore` で除外しているため、導入後の clone / junction / ローカル状態を Git に載せません。

## 何をするリポジトリか

- アーキテクチャで定義された OSS 一式を manifest で管理する
- `Codex_dev` に既にあるローカル repo を clone 元として優先利用する
- ローカルに無いものだけ remote clone する
- すべての導入先を manifest に書かれた `pinnedCommit` に checkout する
- 導入先を `.installed/` に閉じ込めて、制御 repo を汚さない

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

詳細な対応表は [docs/components.md](/Users/ryo-n/Codex_dev/RanD/r-and-d-agent-installer/docs/components.md) を参照してください。

## ディレクトリ構成

```text
r-and-d-agent-installer/
├─ docs/
│  └─ components.md
├─ manifests/
│  └─ components.json
├─ scripts/
│  ├─ install.ps1
│  └─ status.ps1
└─ .gitignore
```

導入後の実体は次に配置されます。

```text
.installed/
├─ repos/
│  ├─ pulse-kestra/
│  ├─ agent-taskstate/
│  ├─ ...
├─ state/
├─ logs/
└─ config/
```

## クイックスタート

PowerShell:

```powershell
Set-Location C:\Users\ryo-n\Codex_dev\RanD\r-and-d-agent-installer
.\scripts\status.ps1
.\scripts\install.ps1
```

ローカル repo を必ず使いたい場合:

```powershell
.\scripts\install.ps1 -Mode local
```

remote clone を強制したい場合:

```powershell
.\scripts\install.ps1 -Mode remote -Force
```

将来差し替え前提の handoff 層を除きたい場合:

```powershell
.\scripts\install.ps1 -SkipOptional
```

## インストール戦略

`install.ps1` は各コンポーネントごとに次の順で判断します。

1. `-Mode auto` か `-Mode local` なら、`localPath` が存在するか確認
2. 存在すれば `.installed/repos/<name>` に junction を作成
3. clone 後に manifest の `pinnedCommit` へ checkout する
4. 既存ターゲットがある場合はスキップし、`-Force` 時のみ再作成

## 補足

- `kestra`, `llm-guard`, `open_deep_research`, `strategy-guided-policy-prompt` は remote clone 前提になりやすいです
- `ai-product-requirement-document` と `workflow-cookbook` はアーキテクチャ上「交換可能な出口層」として optional 扱いです
- ローカル repo の最新状態はこのリポジトリでは更新しません。必要なら各 repo で個別に pull してください
- 導入先は固定コミットへ checkout されるため、GitHub 側やローカル側が更新されても自動追従しません
