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

## 3. 検証コマンド

```powershell
cd research-runtime
python -m unittest discover tests
python -m rand_research.cli heartbeat --dry-run --max-items 2
python -m rand_research.cli env-check
python -m rand_research.cli run-once --preset kano_requirements_offline_eval --max-items 5
```

installer の解決確認:

```powershell
cd ..\r-and-d-agent-installer
.\scripts\status.ps1
```

## 4. 手動確認項目

- [ ] ルート README 先頭に Quickstart がある
- [ ] README に heartbeat / preset 選択規則の表がある
- [ ] README に `status=ok|degraded|failed` と 8 artifact 契約がある
- [ ] README と specification に `research -> insight -> gate -> sync -> notify` の標準チェーンがある
- [ ] README と specification に `agent-taskstate` / `memx-resolver` / `tracker-bridge-materials` の責務境界がある
- [ ] installer README に `CODEX_DEV_ROOT` と override JSON の説明がある
- [ ] runtime README に単体依存と workspace 依存の説明がある
- [ ] specification に schema compatibility policy と最小観測点がある
- [ ] KanoMode の offline eval で `kano.json` と `requirements_packet.json` が保存される

## 5. 残留リスク

- live fetch と live LLM 実行は外部依存に左右されるため、この検収では fixture / local 実行確認を正本とする
- notification / replay / dedupe の実件数は `pulse-kestra` 側の flow output と taskstate 記録に依存する
- peer repo 側の API 変更は `env-check` だけでは完全検知できないため、定期的な統合確認が必要
