# RanD Research Runtime

`research-runtime` は RanD の実行層です。論文・AI ニュースを収集し、正規化し、必要に応じて洞察抽出と Go/Hold/No-Go 評価を行い、artifact と state を保存します。

## 入口

- CLI: `python -m rand_research.cli run-once --preset paper_arxiv_ai_recent`
- CLI: `python -m rand_research.cli run-schedule`
- CLI: `python -m rand_research.cli heartbeat --dry-run`
- PowerShell: `./scripts/run-once.ps1 -Preset paper_arxiv_ai_recent`
- PowerShell: `./scripts/run-schedule.ps1`
- PowerShell: `./scripts/env-check.ps1`

## 入力 / 実行 / 出力

- 入力
  - preset 名
  - `max_items`
  - runtime 設定
  - `state/taskstate.json`
  - `state/memx-journal.json`
- 実行
  - source 収集
  - 正規化
  - 既読判定
  - insight 抽出
  - gate 評価
  - sync payload 生成
  - notify 段への handoff
- 出力
  - `runs/<run_id>/` の 8 artifact
  - `state/` 配下の更新済み snapshot

## 依存の考え方

### `pip install -e .` で入るもの

`research-runtime` 自体は Python 標準ライブラリ中心で構成しています。`pyproject.toml` は editable install と package discovery を提供します。

### 親 repo 経由で満たされる統合依存

次は `pip install -e .` だけでは入りません。RanD 親 repo または installer で導入し、`env-check` で利用可否を確認します。

- `open_deep_research`
- `insight-agent`
- `experiment-gate`
- `agent-taskstate`
- `memx-resolver`
- `tracker-bridge-materials`

統合境界は次で固定します。

- `agent-taskstate`: run / state / decision の正本
- `memx-resolver`: knowledge / read history の正本
- `tracker-bridge-materials`: 外部同期 payload の反映先

### 公開設定 / example / local 設定

- 公開デフォルト
  - `configs/*.json`, README に書かれた既定 preset と heartbeat ルール
- example
  - ルート README の Quickstart、installer の `.env.example`
- local override
  - peer repo の `.env`
  - 実行前に export する環境変数
  - 個人用の runtime 設定差し替え

### `.env` 自動読込で使うもの

起動時に peer repo の `.env` を読み込みます。既定プロバイダは `openrouter`、次点は `alibaba` です。

- `../experiment-gate/.env`
- `../insight-agent/.env`
- `../Roadmap-Design-Skill/.env`
- `../pulse-kestra/bridge/.env`

LLM timeout は最低 600 秒、収集 timeout は最低 180 秒へ底上げします。

## state の更新単位

- run 前
  - `state/taskstate.json` と `state/memx-journal.json` を読みます。
- run 中
  - `queued -> running -> done/needs_review/failed` を更新します。
- run 後
  - `state_context.before/after`
  - `memx_journal.json`
  - `tracker_sync.json`
  - `report.json`
  を保存します。

## 標準チェーン

通常運転の正規経路は `research -> insight -> gate -> sync -> notify` です。`research-runtime` はこのうち `research`, `insight`, `gate`, `sync` までを担当し、replay は途中 stage から再開可能な前提で artifact と state を保存します。

## status と artifact

各 run は `status=ok|degraded|failed` を持ちます。

- `ok`: source / state / report / integrations が正常
- `degraded`: fallback 利用、一部 source 失敗、Insight/Gate/Memx/Tracker の個別失敗
- `failed`: source 全滅、state 読み書き失敗、report 保存失敗

1 run ごとに `runs/<run_id>/` に次を保存します。

- `report.md`
- `report.json`
- `insight.json`
- `gate.json`
- `meta.json`
- `memx_journal.json`
- `tracker_sync.json`
- `state_context.json`

すべての JSON artifact は `schema_version: "1.0"` を持ちます。

## 最小観測点

後から集計できる最小観測点は次です。

- 日次 run 数
- `ok / degraded / failed` 件数
- `report_save_failed` 件数
- `state_write_failed` 件数
- replay 実行件数
- 未通知再送件数
- notification failure 件数
- tracker sync failure 件数
- duplicate suppression 件数

これらのうち runtime が直接持つものは `status`, `status_reason`, `dependency_health`, `tracker_sync.json` に残し、通知・再送・重複抑止は `pulse-kestra` 側の flow output と taskstate で集計します。

## preset と heartbeat

preset は次の 3 つです。

- `paper_arxiv_ai_recent`
- `ai_news_official`
- `ai_watch_daily`

heartbeat の自動選択は `configs/heartbeat.json` を正本にします。現在のルールは JST 基準で次です。

| 時間帯 | preset |
| --- | --- |
| 08:00-11:59 | `ai_watch_daily` |
| 21:00-23:59 | `paper_arxiv_ai_recent` |
| それ以外 | `paper_arxiv_ai_recent` |

## テスト

repo ルートから次で確認できます。

```powershell
python -m unittest discover tests
python -m rand_research.cli heartbeat --dry-run --max-items 2
python -m rand_research.cli env-check
```
