# RanD

`RanD` は、R&D Agent アーキテクチャを「導入層」と「実行層」に分けて束ねる親リポジトリです。固定コミットで周辺 OSS を導入し、論文・AI ニュース調査をローカル実行と Kestra 実行の両方で回しながら、通常運転の正規チェーン `research -> insight -> gate -> sync -> notify` を保つ母艦として振る舞います。

最新リリース: [v0.2.0](docs/releases/v0.2.0.md)

## Quickstart: 5分で1回回す

1. Windows: `install-r-and-d-agent.bat` / macOS・Linux: `./install-r-and-d-agent.sh`
2. Windows: `run-research-once.bat paper_arxiv_ai_recent` / macOS・Linux: `./run-research-once.sh paper_arxiv_ai_recent`
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
  - [install-r-and-d-agent.sh](install-r-and-d-agent.sh)
  - [run-research-once.sh](run-research-once.sh)
  - [run-research-schedule.sh](run-research-schedule.sh)

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
5. Insight / Gate は外部 API を優先し、失敗時はサブエージェント fallback、peer repo Python API、deterministic fallback の順で劣化しながら、正規チェーン `research -> insight -> gate -> sync -> notify` に沿って handoff します。replay は途中 stage から再開可能です。
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

保存済み artifact は runtime CLI で契約を spot check できます。通常確認では `report.json`、KanoMode では `kano.json`、`requirements_packet.json` / `requirements_audit_packet.json`、`downstream_handoff.json` を対象にします。

## KanoMode とは

KanoMode は、狩野モデル参照型の要求分析です。狩野モデルそのものを実施する機能ではありません。

本来の狩野モデルは、ユーザーに「その機能がある場合 / ない場合」を尋ねる調査によって品質属性を分類します。RanD ではその正式調査を行う代わりに、ネット上の不満、称賛、比較、期待、離脱理由、競合言及などの公開証跡を集め、要求候補がどの品質属性に近いかを仮説化します。

正直に言えば、これは低コストな近似です。狩野モデルの厳密な調査結果ではなく、ネットに残った反応から「無いと不満になりそう」「良いほど満足が上がりそう」「あるとうれしいが必須ではなさそう」「逆に嫌がられそう」といった要求の性質を推定します。

特に一元的品質は、競合比較や改善要求に現れやすいものとして扱います。たとえば「もっと速いほどよい」「精度が高いほどよい」「手間が少ないほどよい」「価格に対する価値が高いほどよい」といった反応を集め、良し悪しが満足度に連続的に効いていそうな要求を `performance` として仮分類します。

このため、KanoMode の出力は最終判定ではありません。検索証拠をそのまま要件にせず、`must_be`、`performance`、`attractive`、`reverse`、`questionable` などの仮分類を挟み、confidence、bias_note、kill_condition を付けて、人間レビューや downstream gate に渡します。名前は KanoMode ですが、実体は「Kano-inspired requirements analysis」、つまり狩野モデルのアイデアを借りたネット証跡ベースの要求分析です。

KanoMode には 2 つの使い方があります。

- Discovery mode
  - 新しい要求や調査テーマから、要件候補、KPI 草案、受け入れ条件、リスク、downstream hook を含む `requirements_packet.json` を生成します。
- Audit mode
  - 既存の要件定義を再評価し、価値妥当性、検収可能性、実装整合性を `go / conditional_go / no_go` で見える化した `requirements_audit_packet.json` を生成します。

つまり KanoMode は、要件を「書いたら終わり」にせず、証拠、ユーザー期待、検収可能性、実装整合性で見直すための入口です。生成された packet は `workflow-cookbook` の Task Seed / Acceptance / Evidence、`manual-bb-test-harness` の手動検収観点、`code-to-gate` の実装整合確認へ渡す前提で設計しています。

KanoMode preset では、通常の 8 artifact に加えて次を保存します。

- `kano.json`
  - evidence cluster、Kano参照の仮分類、persona votes、confidence、bias_note、kill_condition を保持します。
- `requirements_packet.json`
  - discovery mode の主契約です。requirements、KPI、acceptance、risks、downstream_hooks、gate_policy を保持します。
- `requirements_audit_packet.json`
  - audit mode の主契約です。既存要件ごとの Kano参照の再分類、testability、implementation_alignment、issues、suggested_action、gate verdict、gate_summary を保持します。
- `downstream_handoff.json`
  - discovery / audit packet を Task Seed、manual BB 観点、code-to-gate contract、tracker dry-run issue へ分解した pilot 用 handoff artifact です。実送信は行いません。

`kano_requirements_hybrid` には live/search shadow adapter があります。既定では無効で、`RAND_KANO_SHADOW_SEARCH=1` を設定した場合だけ検索 URL から evidence を収集します。live evidence は shadow / pilot 用であり、通常検収は fixture / cached corpus を正本にします。

KanoMode の詳細な要件・仕様・検収記録は次を正本にします。

- [KanoMode 要件定義](docs/requirements_kano_mode.md)
- [KanoMode 仕様書](docs/specification_kano_mode.md)
- [KanoMode 引継ぎ資料](docs/kano_mode_handoff.md)
- [KanoMode Eval hardening 検収](docs/acceptance/BB-20260528-02-kano-eval-hardening.md)

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

## 残留リスク

- live fetch と live LLM 実行は外部依存に左右されるため、通常の受け入れでは fixture / local 実行確認を正本にします。
- notification / replay / dedupe の実件数は `pulse-kestra` 側の flow output と taskstate 記録に依存します。
- peer repo 側の API や schema が変わった場合は、`env-check` だけでは完全検知できないため定期的な統合確認が必要です。

## ガバナンスポリシー

RanD は、外部コンポーネント、LLM 呼び出し、fallback 経路、生成 artifact を明示的な信頼境界として扱います。

- [コンポーネント信頼ポリシー](docs/component-trust-policy.md)
- [Fallback ポリシー](docs/fallback-policy.md)
- [Artifact Contract ポリシー](docs/artifact-contract-policy.md)

## preset と heartbeat の選択規則

現在の preset は次の 6 つです。

- `paper_arxiv_ai_recent`
  - [arXiv cs.AI recent](https://arxiv.org/list/cs.AI/recent) を主入口にし、Hugging Face Papers と Papers with Code を補助ソースに使います。
- `ai_news_official`
  - OpenAI News、Anthropic News、Google DeepMind Blog、Google AI Blog を巡回します。
- `ai_watch_daily`
  - `paper_arxiv_ai_recent` と `ai_news_official` の合成 preset です。
- `kano_requirements_hybrid`
  - KanoMode の query family から要求候補 evidence seed を生成し、`kano.json` と `requirements_packet.json` を保存します。
- `kano_requirements_offline_eval`
  - fixture evidence だけで KanoMode の artifact 契約を検証する再現性重視の preset です。
- `kano_requirements_audit`
  - 既存要件定義の監査用 preset です。fixture evidence から `kano.json` と `requirements_audit_packet.json` を生成し、Requirement Definition Gate の `go / conditional_go / no_go` 分布を確認します。

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

運用メトリクスと pending 通知を見る:

```powershell
cd research-runtime
python -m rand_research.cli pilot-check
python -m rand_research.cli metrics
python -m rand_research.cli resend-pending --limit 10
python -m rand_research.cli shadow-eval-template --run-dir runs/<run_id> --format csv
python -m rand_research.cli tracker-review --path runs/<run_id>/downstream_handoff.json
python -m rand_research.cli generate-task-seeds --handoff runs/<run_id>/downstream_handoff.json
python -m rand_research.cli validate-artifact --path runs/<run_id>/downstream_handoff.json
```

`pilot-check` は latest run、artifact schema、operations outbox、heartbeat config、メトリクスをまとめて確認し、`go / degraded / no_go` を返します。常時運転へ出す前の軽量 gate として扱います。

KanoMode の offline eval を回す:

```powershell
cd research-runtime
python -m rand_research.cli run-once --preset kano_requirements_offline_eval --max-items 5
```

KanoMode の audit eval を回す:

```powershell
cd research-runtime
python -m rand_research.cli run-once --preset kano_requirements_audit --max-items 5
```

Windows 環境で `python` が Windows Store stub に当たる場合は、`uv run python` で同じコマンドを実行してください。

macOS / Linux では次の入口を使えます。

```bash
./install-r-and-d-agent.sh
./run-research-once.sh paper_arxiv_ai_recent
./run-research-schedule.sh
cd research-runtime
./scripts/env-check.sh
```

`install-r-and-d-agent.sh` は PowerShell installer を `pwsh` で呼び出します。runtime の `*.sh` は `bash` と `python` だけで動きます。

Insight / Gate を外部 API 経由で動かす場合は、必要に応じて次を設定します。API が失敗した場合は、設定済みのサブエージェントコマンドへ同じ JSON payload を stdin で渡します。

```bash
export RAND_INSIGHT_API_URL="https://example.test/insight"
export RAND_GATE_API_URL="https://example.test/gate"
export RAND_INSIGHT_SUBAGENT_CMD="your-insight-agent-command"
export RAND_GATE_SUBAGENT_CMD="your-gate-agent-command"
```

## KanoMode Eval 検証状況

2026-05-29 JST 時点で、KanoMode の fixture-based release gate は Go です。これは live web search や LLM provider の分類品質を本番保証するものではなく、固定 fixture / golden / black-box CLI / Code-to-gate による再現性検収を指します。

検証済み:

- `uv run pytest`
  - `64 passed`
- `uv run python -m rand_research.cli run-once --preset kano_requirements_offline_eval --max-items 5`
  - run_id `20260528-150341-856a486c`
  - `status: ok`
  - `kano.json` と `requirements_packet.json` を生成
  - promoted `REQ-001` / `KC-001`
  - low-confidence attractive `KC-002` は `confidence below 0.7 threshold` で昇格拒否
- `uv run python -m rand_research.cli run-once --preset kano_requirements_audit --max-items 5`
  - run_id `20260528-150341-cf9c8e40`
  - `status: ok`
  - `requirements_audit_packet.json` を生成
  - `overall_assessment: no_go`
  - verdict distribution: `go=1`, `conditional_go=1`, `no_go=1`
- `code-to-gate analyze`
  - run_id `ctg-202605281503`
  - Critical 0 / High 0 / Medium 0 / Low 0 / Suppressed 0

KanoMode Eval の合格条件は「すべてを Go と判定すること」ではありません。実行成功の `status=ok` と、要件監査の `overall_assessment` を分離し、No-Go 条件を No-Go として止められることを正とします。

state 保存は atomic write と file lock に対応済みです。2026-05-28 に発生した並列 CLI 実行時の `state_write_failed` は [TASK-20260528-03](docs/tasks/TASK-20260528-03-parallel-state-write-hardening.md) で hardening 済みです。
