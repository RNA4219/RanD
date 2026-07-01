# RanD Evaluation

## 1. 目的

本書は [requirements.md](requirements.md) と [specification.md](specification.md) に対する受け入れ基準と確認手順を定義する。

## 2. Acceptance Criteria

| ID | 観点 | 判定方法 |
| --- | --- | --- |
| AC-01 | installer 可搬性 | `components.json` に絶対ローカルパスが無い |
| AC-02 | heartbeat 選択 | `heartbeat --dry-run` が preset と timezone を返す |
| AC-03 | unittest 導線 | `python -m unittest discover tests` が通る |
| AC-04 | report schema | `report.json` に `schema_version`, `status`, `status_reason`, `state_context`, `artifacts` がある |
| AC-05 | state_context schema | `state_context.json` に `schema_version`, `before`, `after` がある |
| AC-06 | memx / tracker schema | root と entry/event に `schema_version` がある |
| AC-07 | fixture 回帰 | arXiv / RSS / generic link の fixture テストが通る |
| AC-08 | docs 整合 | README / requirements / specification が heartbeat 規則と status 契約で一致する |
| AC-09 | failure source 分離 | `dependency_health.report` があり、`report_save_failed` と `state_write_failed` を区別できる |
| AC-10 | 観測点契約 | 最小観測点を後から集計できる field / log の定義が README / specification / evaluation にある |
| AC-11 | 標準チェーン | README / specification が `research -> insight -> gate -> sync -> notify` を正規経路として扱う |
| AC-12 | macOS / Linux 入口 | `run-research-once.sh`, `run-research-schedule.sh`, `research-runtime/scripts/*.sh` が存在し、runtime が PowerShell 非依存で起動できる |
| AC-13 | API / subagent fallback | Insight / Gate が外部 API を優先し、API 失敗時にサブエージェント fallback を試す unit test が通る |
| AC-14 | Code-to-gate release gate | `code-to-gate analyze` の effective High/Critical finding が 0、または Task Seed / Acceptance に根拠付き follow-up がある |

### 2.1 KanoMode Acceptance Criteria

KanoMode の詳細な要件は [requirements_kano_mode.md](requirements_kano_mode.md) を正本とする。

| ID | 観点 | 判定方法 |
| --- | --- | --- |
| AC-K01 | Kano preset | `kano_requirements_hybrid` preset が存在する |
| AC-K02 | offline eval | live web なしで fixture / cached corpus による評価導線がある |
| AC-K03 | Kano artifact | `kano.json` が `schema_version`, `mode`, `request_id`, `topic`, `persona_modes`, `source_summary`, `kano_candidates`, `known_biases` を持つ。`kano_candidates[*]` が `candidate_id`, `statement`, `kano_type`, `confidence`, `evidence`, `persona_votes`, `bias_note`, `kill_condition` を持つ |
| AC-K04 | requirements packet | `requirements_packet.json` が `schema_version`, `packet_id`, `derived_from`, `product_context`, `assumptions`, `requirements`, `release_readiness_prelude` を持つ。`requirements[*]` が `requirement_id`, `title`, `statement`, `kano_type`, `priority`, `confidence`, `evidence_refs`, `kpi`, `acceptance_criteria`, `risks`, `manual_bb_focus`, `downstream_hooks`, `gate_policy`, `bias_note`, `kill_condition` を持つ |
| AC-K05 | safety fields | confidence, bias_note, kill_condition 欠損時に packet 昇格しない |
| AC-K06 | compatibility | 既存 preset の `python -m unittest discover tests` が通る |
| AC-K07 | audit artifact | `requirements_audit_packet.json` の root と requirement item の必須 field が仕様化されている |
| AC-K08 | requirement gate | Requirement Definition Gate が `go`, `conditional_go`, `no_go` の判定基準を持つ |
| AC-K09 | downstream audit hooks | manual-bb-test-harness と code-to-gate の役割分担が仕様化されている |
| AC-K10 | KanoMode の位置づけ | 狩野モデルそのものではなく、ネット証跡から品質分類を仮説化するモードだと README / requirements / specification に明記されている |
| AC-K11 | 一元的品質の疑似再現 | `performance` がネット上の比較・改善要求・悪化時不満から疑似再現する仮分類だと説明されている |
| AC-K12 | Eval gate semantics | `status=ok` は runtime 実行成功、`gate_summary.overall_assessment` は要件監査判定として分離されている。`no_go` 要件が 1 件でもある audit fixture では overall が `no_go` になる |
| AC-K13 | Promotion gate | `requirements_packet` 昇格には confidence 閾値、安全 field、証拠 tier、Kano type の条件があり、低 confidence / `questionable` / 証拠不足候補を昇格しない |
| AC-K14 | Golden Eval | discovery / audit の fixture に対して promoted requirements、verdict distribution、overall assessment を golden 期待値として検証する |
| AC-K15 | Shadow search | `kano_shadow_search` は既定無効で、`RAND_KANO_SHADOW_SEARCH=1` の場合だけ live/search evidence を収集する |
| AC-K16 | Downstream handoff | KanoMode run が `downstream_handoff.json` を保存し、Task Seed / manual BB / code-to-gate / tracker dry-run issue を含む |
| AC-K17 | Operations metrics | `metrics`, `resend-pending`, `replay-plan` CLI が state / runs から運用情報を返す |
| AC-K18 | Artifact validation | `validate-artifact` CLI が主要 JSON artifact の必須 field と入れ子 `schema_version` を検査できる |
| AC-K19 | Pilot readiness gate | `pilot-check` CLI が latest run、artifact schema、operations state、heartbeat config、metrics を集約し、`go / degraded / no_go` を返す |

## 3. 検証コマンド

```powershell
cd research-runtime
python -m unittest discover tests
python -m rand_research.cli heartbeat --dry-run --max-items 2
python -m rand_research.cli env-check
python -m rand_research.cli run-once --preset kano_requirements_offline_eval --max-items 5
python -m rand_research.cli run-once --preset kano_requirements_audit --max-items 5
python -m rand_research.cli pilot-check
python -m rand_research.cli metrics
python -m rand_research.cli resend-pending --limit 10
python -m rand_research.cli shadow-eval-template --run-dir runs/<run_id> --format json
python -m rand_research.cli tracker-review --path runs/<run_id>/downstream_handoff.json
python -m rand_research.cli generate-task-seeds --handoff runs/<run_id>/downstream_handoff.json
python -m rand_research.cli validate-artifact --path runs/<run_id>/downstream_handoff.json
```

macOS / Linux runtime 入口:

```bash
cd research-runtime
./scripts/env-check.sh
./scripts/run-once.sh paper_arxiv_ai_recent 2
```

installer の解決確認:

```powershell
cd ..\r-and-d-agent-installer
.\scripts\status.ps1
```

Code-to-gate gate:

```powershell
cd C:\Users\ryo-n\Codex_dev\RanD
node C:\Users\ryo-n\Codex_dev\code-to-gate\dist\cli.js analyze C:\Users\ryo-n\Codex_dev\RanD --emit all --out C:\tmp\rand-code-to-gate-clean --llm-provider deterministic --cache force --ignore research-runtime/runs,research-runtime/state,research-runtime/.pytest_cache,research-runtime/src/rand_research_runtime.egg-info
```

判定:

- Critical / High の effective finding は release 前に 0 にする。
- やむをえず残す場合は、`docs/tasks/` の Task Seed と `docs/acceptance/` の Acceptance Record に、根拠、影響、期限つき follow-up を記録する。

## 4. 手動確認項目

- [x] ルート README 先頭に Quickstart がある
- [x] README に heartbeat / preset 選択規則の表がある
- [x] README に `status=ok|degraded|failed` と 8 artifact 契約がある
- [x] README と specification に `research -> insight -> gate -> sync -> notify` の標準チェーンがある
- [x] README と specification に `agent-taskstate` / `memx-resolver` / `tracker-bridge-materials` の責務境界がある
- [x] installer README に `CODEX_DEV_ROOT` と override JSON の説明がある
- [x] runtime README に単体依存と workspace 依存の説明がある
- [x] specification に schema compatibility policy と最小観測点がある
- [x] KanoMode の offline eval で `kano.json` と `requirements_packet.json` が保存される
- [x] KanoMode audit eval で `requirements_audit_packet.json` が保存され、`status=ok` と `overall_assessment` を別々に確認できる
- [x] KanoMode Eval の golden fixture が discovery / audit の期待値を検証している
- [x] JSON artifact の必須 field は `validate-artifact` CLI で spot check できる
- [x] pilot runtime readiness は `pilot-check` CLI で一括確認できる
- [x] Code-to-gate report の High/Critical finding が 0、または follow-up が記録されている

## 5. 残留リスク

- live fetch と live LLM 実行は外部依存に左右されるため、この検収では fixture / local 実行確認を正本とする
- notification / replay / dedupe の実件数は `pulse-kestra` 側の flow output と taskstate 記録に依存する
- peer repo 側の API 変更は `env-check` だけでは完全検知できないため、定期的な統合確認が必要
