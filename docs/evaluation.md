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

## 3. 検証コマンド

```powershell
cd research-runtime
python -m unittest discover tests
python -m rand_research.cli heartbeat --dry-run --max-items 2
python -m rand_research.cli env-check
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

## 5. 残留リスク

- live fetch と live LLM 実行は外部依存に左右されるため、この検収では fixture / local 実行確認を正本とする
- notification / replay / dedupe の実件数は `pulse-kestra` 側の flow output と taskstate 記録に依存する
- peer repo 側の API 変更は `env-check` だけでは完全検知できないため、定期的な統合確認が必要
