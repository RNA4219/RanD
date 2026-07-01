# RanD Research Runtime

`research-runtime` は RanD の実行層です。論文・AI ニュースを収集し、正規化し、必要に応じて洞察抽出と Go/Hold/No-Go 評価を行い、artifact と state を保存します。

## 入口

- CLI: `python -m rand_research.cli run-once --preset paper_arxiv_ai_recent`
- CLI: `python -m rand_research.cli run-once --preset kano_requirements_offline_eval --max-items 5`
- CLI: `python -m rand_research.cli run-schedule`
- CLI: `python -m rand_research.cli heartbeat --dry-run`
- PowerShell: `./scripts/run-once.ps1 -Preset paper_arxiv_ai_recent`
- PowerShell: `./scripts/run-schedule.ps1`
- PowerShell: `./scripts/env-check.ps1`
- Bash: `./scripts/run-once.sh paper_arxiv_ai_recent`
- Bash: `./scripts/run-schedule.sh`
- Bash: `./scripts/env-check.sh`

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
  - KanoMode discovery preset では追加で `kano.json` と `requirements_packet.json`
  - KanoMode audit preset では追加で `kano.json` と `requirements_audit_packet.json`
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

Insight / Gate の実行は、外部 API を最優先にします。

- `RAND_INSIGHT_API_URL`, `RAND_GATE_API_URL`: HTTP API endpoint
- `RAND_INSIGHT_API_TOKEN`, `RAND_GATE_API_TOKEN`: 任意の bearer token
- `RAND_INSIGHT_SUBAGENT_CMD`, `RAND_GATE_SUBAGENT_CMD`: API 失敗時に stdin JSON を受け取るサブエージェントコマンド
- `RAND_INTEGRATION_TIMEOUT_SECONDS`: API / subagent timeout

API とサブエージェントが使えない場合は、peer repo の Python API を試し、それも失敗したら deterministic fallback を `degraded` として保存します。

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

state ファイルは atomic write で更新します。途中失敗で壊れた JSON が残ると次回 run の `state_write_failed` につながるため、書き込みは一時ファイル経由で完了させます。

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

## KanoMode

KanoMode は、狩野モデルそのものを実施するものではなく、狩野モデルの品質分類を参照してネット証跡から要求候補を仮分類する実行モードです。正式なアンケートではなく、収集済み evidence や fixture evidence を要求定義向けの artifact に変換します。通常の research chain を壊さず、`research -> insight -> gate -> sync -> notify` の流れに追加 artifact を載せます。

Discovery mode では、complaints / praise / compare / expectation などのネット上の信号をもとに要件候補を分類し、`requirements_packet.json` を生成します。特に `performance` は一元的品質をネット経由で疑似再現する分類で、競合比較、速度、精度、手間、価格など「良いほど満足が上がる」反応の束から推定します。この packet は、要求文、KPI、受け入れ条件、リスク、手動 BB 観点、downstream hook、gate policy を含みます。

Audit mode では、既存要件定義を監査対象として読み、各要件を Kano参照の仮分類、検収可能性、実装整合性、残リスクで評価します。結果は `requirements_audit_packet.json` に保存し、Requirement Definition Gate の `go / conditional_go / no_go` 判定として扱います。

KanoMode の受け入れでは live web search を必須にしません。再現性のある fixture / cached corpus による offline eval を正本にし、live search は pilot / shadow eval として扱います。

`kano_requirements_hybrid` には live/search pilot 用の `kano_shadow_search` adapter があります。既定では無効で、`RAND_KANO_SHADOW_SEARCH=1` を設定した場合だけ設定済み検索 URL から shadow evidence を収集します。収集結果は通常の `kano.json` / `requirements_packet.json` へ混ぜられますが、検索順位や SEO ノイズを含むため、通常受け入れの正本にはしません。

KanoMode discovery preset では、上記に加えて次を保存します。

- `kano.json`
  - evidence cluster、Kano参照の仮分類、persona votes、confidence、bias_note、kill_condition
- `requirements_packet.json`
  - requirements、KPI、acceptance、risks、downstream_hooks、gate_policy

KanoMode audit preset では、上記に加えて次を保存します。

- `kano.json`
  - audit evidence をもとにした Kano参照の再分類と gatekeeper vote
- `requirements_audit_packet.json`
  - 既存要件ごとの `testability`, `implementation_alignment`, `issues`, `suggested_action`, `gate_verdict`
  - `gate_summary` に `go / conditional_go / no_go` の分布と overall assessment

KanoMode の packet 生成時は追加で `downstream_handoff.json` を保存します。これは `requirements_packet.json` または `requirements_audit_packet.json` を、`workflow-cookbook` の Task Seed、`manual-bb-test-harness` のテスト観点、`code-to-gate` の phase contract、`tracker-bridge-materials` の dry-run issue へ分解した handoff artifact です。実送信は行わず、pilot / review 用の dry-run 契約として扱います。

## Operations CLI

通知・再送・重複抑止・replay は `state/operations-state.json` に記録します。runtime は直接 Misskey へ送信せず、pending outbox と replay plan を残します。

```powershell
python -m rand_research.cli metrics
python -m rand_research.cli resend-pending --limit 10
python -m rand_research.cli replay-plan --task-id <task-id>
python -m rand_research.cli mark-notification --notification-id <id> --status sent
python -m rand_research.cli shadow-eval-template --run-dir runs/<run_id> --format csv
python -m rand_research.cli tracker-review --path runs/<run_id>/downstream_handoff.json
python -m rand_research.cli generate-task-seeds --handoff runs/<run_id>/downstream_handoff.json
```

`metrics` は `runs/` と `state/` から、日次 run 数、`ok / degraded / failed` 件数、`state_write_failed`、未通知数、replay 件数、duplicate suppression 件数などを集計します。

`shadow-eval-template` は live/search shadow evidence を人手評価するための JSON/CSV テンプレを出力します。`tracker-review` は tracker dry-run issue に `ready_to_send=false` のレビュー台帳を付けます。`generate-task-seeds` は既定 dry-run で Task Seed draft を返し、ファイルへ書く場合だけ `--write` を付けます。

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

preset は次の 6 つです。

- `paper_arxiv_ai_recent`
- `ai_news_official`
- `ai_watch_daily`
- `kano_requirements_hybrid`
- `kano_requirements_offline_eval`
- `kano_requirements_audit`

KanoMode の通常検証では live web search を必須にせず、`kano_requirements_offline_eval` と `kano_requirements_audit` の fixture / cached corpus を正本にします。

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
python -m rand_research.cli run-once --preset kano_requirements_offline_eval --max-items 5
python -m rand_research.cli run-once --preset kano_requirements_audit --max-items 5
```

macOS / Linux では同じ確認を shell wrapper でも実行できます。

```bash
./scripts/env-check.sh
./scripts/run-once.sh kano_requirements_offline_eval 5
```

Windows 環境で `python` が Windows Store stub に当たる場合は、`uv run python` に置き換えて実行します。

2026-05-29 JST 時点の KanoMode Eval 検証結果:

- pytest: `64 passed`
- discovery offline eval:
  - run_id `20260528-150341-856a486c`
  - `status: ok`
  - `kano.json` と `requirements_packet.json` を生成
  - promoted `REQ-001` / `KC-001`
  - low-confidence attractive `KC-002` は `confidence below 0.7 threshold` で昇格拒否
- audit eval:
  - run_id `20260528-150341-cf9c8e40`
  - `status: ok`
  - `requirements_audit_packet.json` を生成
  - `overall_assessment: no_go`
  - verdict distribution: `go=1`, `conditional_go=1`, `no_go=1`
- Code-to-gate:
  - run_id `ctg-202605281503`
  - Critical 0 / High 0 / Medium 0 / Low 0 / Suppressed 0

KanoMode Eval の release gate は fixture-based Go です。live web search と LLM provider の分類品質は別途 pilot / shadow eval の対象であり、この通常検収の必須条件にはしません。
