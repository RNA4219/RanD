# RanD

`RanD` は、R&D Agent アーキテクチャを「導入層」と「実行層」に分けて束ねる親リポジトリです。固定コミットで周辺 OSS を導入し、論文・AI ニュース調査をローカル実行と Kestra 実行の両方で回しながら、通常運転の正規チェーン `research -> insight -> gate -> sync -> notify` を保つ母艦として振る舞います。

## Quickstart: 5分で1回回す

1. `install-r-and-d-agent.bat`
2. `run-research-once.bat paper_arxiv_ai_recent`
3. `research-runtime/runs/<run_id>/report.md` を開く

最短導線だけ先に使いたい場合は上の 3 手順で十分です。設計の正本を確認したい場合は次の順で読んでください。

- [アーキテクチャ](docs/architecture.md)
- [要件定義](docs/requirements.md)
- [仕様書](docs/specification.md)
- [検収基準](docs/evaluation.md)

## 入口

- [導入用リポジトリ](r-and-d-agent-installer/README.md)
- [調査ランタイム](research-runtime/README.md)
- [Kestra flow 定義](kestra/README.md)
- ルート入口バッチ
  - [install-r-and-d-agent.bat](install-r-and-d-agent.bat)
  - [run-research-once.bat](run-research-once.bat)
  - [run-research-schedule.bat](run-research-schedule.bat)

## リポジトリが束ねる2層

- 導入層
  - `r-and-d-agent-installer` が必要な OSS 群を固定コミットで導入します。
  - 実体は `r-and-d-agent-installer/.installed/` に配置し、Git では管理しません。
- 実行層
  - `research-runtime` が preset に従って source を巡回し、収集、正規化、洞察、評価、state 保存、外部同期 payload 生成まで担当します。
  - `kestra/flows/` は `research-runtime` を定期実行またはイベント起点で呼び出す flow 定義です。

## 導入層に含まれるアプリケーション

- [`open_deep_research`](https://github.com/langchain-ai/open_deep_research)
- [`llm-guard`](https://github.com/protectai/llm-guard)
- [`kestra`](https://github.com/kestra-io/kestra)
- [`pulse-kestra`](https://github.com/RNA4219/pulse-kestra)
- [`agent-taskstate`](https://github.com/RNA4219/agent-taskstate)
- [`experiment-gate`](https://github.com/RNA4219/experiment-gate)
- [`ai-product-requirement-document`](https://github.com/RNA4219/ai-product-requirement-document)
- [`Roadmap-Design-Skill`](https://github.com/RNA4219/Roadmap-Design-Skill)
- [`strategy-guided-policy-prompt`](https://github.com/RNA4219/strategy-guided-policy-prompt)
- [`insight-agent`](https://github.com/RNA4219/insight-agent)
- [`memx-resolver`](https://github.com/RNA4219/memx-resolver)
- [`tracker-bridge-materials`](https://github.com/RNA4219/tracker-bridge-materials)
- [`workflow-cookbook`](https://github.com/RNA4219/workflow-cookbook)

## どう動くか

1. `install-r-and-d-agent.bat` が導入対象 OSS を pinned commit で配置します。
2. `run-research-once.bat <preset>` か `run-research-schedule.bat` が `research-runtime` を起動します。
3. `research-runtime` は `agent-taskstate` を run / state / decision の正本として読み、`memx-resolver` を knowledge / read history の正本として参照します。
4. source を収集し、`NormalizedItem` に正規化し、既読 URL と重複を整理します。
5. `insight-agent` と `experiment-gate` を順に呼び、正規チェーン `research -> insight -> gate -> sync -> notify` に沿って handoff します。replay は途中 stage から再開可能です。
6. `tracker-bridge-materials` は外部同期 payload の反映先として扱い、`agent-taskstate` 形式の task state、`memx-resolver` 向け journal、`tracker-bridge-materials` 向け sync payload を更新します。
7. `research-runtime/runs/<run_id>/` に 8 種の artifact を保存し、通知・再送・重複抑止のための集計元フィールドも残します。

## status と成果物契約

各 run はトップレベル `status` を持ちます。

- `ok`: source / state / report / integrations がすべて正常
- `degraded`: 一部 source 失敗、Insight/Gate/Memx/Tracker の個別失敗、fallback 利用あり
- `failed`: source 全滅、state 読み書き失敗、report 保存失敗

`taskstate` への写像は次です。

- `ok -> done`
- `degraded -> needs_review`
- `failed -> failed`

`research-runtime/runs/<run_id>/` には次を保存します。

- `report.md`
- `report.json`
- `insight.json`
- `gate.json`
- `meta.json`
- `memx_journal.json`
- `tracker_sync.json`
- `state_context.json`

JSON artifact には `schema_version: "1.0"` を持たせています。`report.json` には最低でも `schema_version`, `status`, `status_reason`, `state_context`, `artifacts`, `dependency_health` が入り、`dependency_health.report` によって artifact 保存障害を `state` 障害と分離して観測できます。

## 標準チェーンと責務境界

通常運転の正規経路は `research -> insight -> gate -> sync -> notify` です。

- `RanD` の責務は、この chaining 順序と handoff 契約を束ねることです。
- replay は途中 stage から再開可能です。
- `agent-taskstate` は run / state / decision の正本です。
- `memx-resolver` は knowledge / read history の正本です。
- `tracker-bridge-materials` は外部同期 payload の反映先です。

## 最小観測点

今の実装では、次の観測点を後から集計できるように field と log を定義しています。

- 日次 run 数
- `ok / degraded / failed` 件数
- `report_save_failed` 件数
- `state_write_failed` 件数
- replay 実行件数
- 未通知再送件数
- notification failure 件数
- tracker sync failure 件数
- duplicate suppression 件数

## preset と heartbeat の選択規則

現在の preset は次の 3 つです。

- `paper_arxiv_ai_recent`
  - [arXiv cs.AI recent](https://arxiv.org/list/cs.AI/recent) を主入口にし、Hugging Face Papers と Papers with Code を補助ソースに使います。
- `ai_news_official`
  - OpenAI News、Anthropic News、Google DeepMind Blog、Google AI Blog を巡回します。
- `ai_watch_daily`
  - `paper_arxiv_ai_recent` と `ai_news_official` の合成 preset です。

heartbeat の自動選択は JST 基準で次の規則です。

| 時間帯 | 選択 preset |
| --- | --- |
| 08:00-11:59 | `ai_watch_daily` |
| 21:00-23:59 | `paper_arxiv_ai_recent` |
| それ以外 | `paper_arxiv_ai_recent` |

- この表は preset 選択規則の正本です。
- 定時実行の時刻そのものは `kestra/flows/research-ai-watch-daily.yaml` と `kestra/flows/research-arxiv-nightly.yaml` の cron で管理します。
- `research-heartbeat.yaml` は event/manual 起点で preset を補完するための flow です。
- CLI で `--preset` を明示した場合は時間帯規則より優先します。
- 合成 preset では child preset のどれか 1 つでも `degraded` なら親も `degraded`、すべて `failed` なら親も `failed` です。

## Kestra を使う場合の流れ

正規の E2E は `pulse-kestra -> Kestra -> guard -> research -> insight -> gate -> sync -> notify` です。

1. `pulse-kestra` が mention / webhook / cron / heartbeat を受けます。
2. `Kestra` が flow を起動します。
3. 必要なら `llm-guard` を入口と出口に挟みます。
4. `research-runtime` が research 実行を担当します。
5. `agent-taskstate`, `memx-resolver`, `tracker-bridge-materials` 向けの状態と payload を保存し、通知段へ handoff します。

現在持っている flow は次の 4 本です。

- [research-manual-run.yaml](kestra/flows/research-manual-run.yaml)
- [research-ai-watch-daily.yaml](kestra/flows/research-ai-watch-daily.yaml)
- [research-arxiv-nightly.yaml](kestra/flows/research-arxiv-nightly.yaml)
- [research-heartbeat.yaml](kestra/flows/research-heartbeat.yaml)

## セットアップと実行

通常インストール:

```bat
install-r-and-d-agent.bat
```

1 回だけ論文調査を回す:

```bat
run-research-once.bat paper_arxiv_ai_recent
```

スケジュール定義をまとめて回す:

```bat
run-research-schedule.bat
```

heartbeat の選択結果だけ見る:

```powershell
cd research-runtime
python -m rand_research.cli heartbeat --dry-run --max-items 5
```

依存と API 設定を確認する:

```powershell
cd research-runtime
.\scripts\env-check.ps1
```
