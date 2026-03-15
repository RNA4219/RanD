# RanD Research Runtime

`research-runtime` は RanD の実行層です。論文・AI ニュースを収集し、正規化し、必要に応じて洞察抽出と Go/Hold/No-Go 評価を行い、artifact と state を保存します。

## 入口

- CLI: `python -m rand_research.cli run-once --preset paper_arxiv_ai_recent`
- CLI: `python -m rand_research.cli run-schedule`
- CLI: `python -m rand_research.cli heartbeat --dry-run`
- PowerShell: `./scripts/run-once.ps1 -Preset paper_arxiv_ai_recent`
- PowerShell: `./scripts/run-schedule.ps1`
- PowerShell: `./scripts/env-check.ps1`

## 依存の考え方

### `pip install -e .` で入るもの

`research-runtime` 自体は Python 標準ライブラリ中心で構成しているため、単体依存は最小です。`pyproject.toml` では editable install と package discovery を提供します。

### 親 repo 経由で満たされる統合依存

次は `pip install -e .` だけでは入りません。RanD 親 repo または installer で導入し、`env-check` で利用可否を確認します。

- `open_deep_research`
- `insight-agent`
- `experiment-gate`
- `agent-taskstate`
- `memx-resolver`
- `tracker-bridge-materials`

### `.env` 自動読込で使うもの

起動時に peer repo の `.env` を読み込みます。既定プロバイダは `openrouter`、次点は `alibaba` です。

- `../experiment-gate/.env`
- `../insight-agent/.env`
- `../Roadmap-Design-Skill/.env`
- `../pulse-kestra/bridge/.env`

LLM timeout は最低 600 秒、収集 timeout は最低 180 秒へ底上げします。

## ディレクトリ構成

```text
research-runtime/
├─ configs/
├─ prompts/
├─ scripts/
├─ src/rand_research/
├─ state/
├─ runs/
└─ tests/
```

## status と state-aware 実行

各 run は `status=ok|degraded|failed` を持ちます。

- `ok`: source / state / integrations が正常
- `degraded`: fallback 利用、一部 source 失敗、Insight/Gate/Memx/Tracker の個別失敗
- `failed`: source 全滅、state 読み書き失敗、report 保存失敗

実行前後では次を扱います。

- `state/taskstate.json` を読んで同一 preset の過去 task を把握
- `state/memx-journal.json` を読んで既読 URL を把握
- 実行中に `queued -> running -> done/needs_review/failed` を記録
- 実行後に `state_context.before/after` を artifact に保存

## 成果物

1 run ごとに `runs/<run_id>/` に次を保存します。

- `report.md`
- `report.json`
- `insight.json`
- `gate.json`
- `meta.json`
- `memx_journal.json`
- `tracker_sync.json`
- `state_context.json`

すべての JSON artifact は `schema_version: "1.0"` を持ちます。`report.json` には少なくとも次が含まれます。

- `schema_version`
- `status`
- `status_reason`
- `dependency_health`
- `state_context`
- `artifacts`

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

- `--preset` を指定した場合は手動指定を優先します。
- `ai_watch_daily` は child preset の status を集約します。

## テスト

repo ルートから次で確認できます。

```powershell
python -m unittest discover tests
python -m rand_research.cli heartbeat --dry-run --max-items 2
python -m rand_research.cli env-check
```
