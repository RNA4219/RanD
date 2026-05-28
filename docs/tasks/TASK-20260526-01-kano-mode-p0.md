---
task_id: TASK-20260526-01
intent_id: INT-KANO-001
owner: rand
status: superseded
last_reviewed_at: 2026-05-28
next_review_due: null
superseded_by: TASK-20260528-02
completion_evidence: docs/acceptance/AC-20260528-02.md
---

# Task Seed: KanoMode P0

## メタデータ

```yaml
task_id: TASK-20260526-01
repo: RanD
base_branch: main
work_branch: codex/kano-mode-p0
priority: P0
langs: [python, markdown, json]
```

## Objective

RanD の `research-runtime` に KanoMode MVP の入口を追加し、検索証拠から `kano.json` と `requirements_packet.json` を生成できる最小実装を作る。

## Scope

- In:
  - `research-runtime/configs/presets/*`
  - `research-runtime/prompts/*`
  - `research-runtime/src/rand_research/fetchers.py`
  - `research-runtime/src/rand_research/integrations.py`
- `research-runtime/src/rand_research/reports.py`
- `research-runtime/src/rand_research/pipeline.py`
- `research-runtime/src/rand_research/kano.py`
- `research-runtime/tests/*`
  - `docs/requirements_kano_mode.md`
- Out:
  - 新規 OSS 作成
  - peer repo 側の API 破壊的変更
  - 本番 tracker / SaaS 認証
  - Kestra 定期 flow の本格追加

## Requirements

- Behavior:
  - `run-once --preset kano_requirements_hybrid` で KanoMode 実行線に入れること
  - query family から complaint / praise / compare / expectation 系の evidence seed を組み立てること
  - 複数 evidence を要求候補 cluster に束ね、persona-aware insight payload を生成すること
  - `kano.json` と `requirements_packet.json` を run directory に保存すること
  - confidence, bias_note, kill_condition が欠ける候補は requirements packet に昇格しないこと
- I/O Contract:
  - Input: preset JSON, topic, locale, query family, source metadata
  - Output: `kano.json`, `requirements_packet.json`, existing report artifacts
- Constraints:
  - 既存 preset と既存 artifact 契約を破壊しない
  - live web search は acceptance の必須条件にしない
  - 新規 JSON artifact は `schema_version` を必須にする
  - Python 変更は既存 unittest を通す
- Acceptance Criteria:
  - `kano_requirements_hybrid` preset が存在する
  - `kano_requirements_offline_eval` または同等の fixture 導線が存在する
  - `kano.json` sample / fixture が schema 期待キーを満たす
  - `requirements_packet.json` sample / fixture が KPI / acceptance / risk を持つ
  - 既存 `python -m unittest discover tests` が通る

## Affected Paths

- `research-runtime/configs/presets/*.json`
- `research-runtime/prompts/*`
- `research-runtime/src/rand_research/fetchers.py`
- `research-runtime/src/rand_research/integrations.py`
- `research-runtime/src/rand_research/reports.py`
- `research-runtime/src/rand_research/pipeline.py`
- `research-runtime/src/rand_research/models.py`
- `research-runtime/tests/*`
- `docs/requirements_kano_mode.md`
- `docs/evaluation.md`
- `docs/specification.md`
- `README.md`

## Local Commands

```powershell
cd research-runtime
python -m unittest discover tests
python -m rand_research.cli heartbeat --dry-run --max-items 2
python -m rand_research.cli env-check
python -m rand_research.cli run-once --preset kano_requirements_offline_eval --max-items 5
```

## Deliverables

- preset:
  - `kano_requirements_hybrid`
  - `kano_requirements_offline_eval`
- artifacts:
  - `kano.json`
  - `requirements_packet.json`
- tests:
  - query family expansion
  - cluster payload generation
  - artifact save
  - packet validation
- docs:
  - README の KanoMode 入口
  - specification の artifact 契約
  - evaluation の AC-K 系検収条件

## Plan

### Steps

1. 現状把握: preset / fetcher / integration / report 保存の責務を確認する
2. preset と prompt を追加し、KanoMode の設定入口を作る
3. query family expansion と offline fixture fetcher を実装する
4. evidence cluster と persona-aware insight payload を実装する
5. `kano.json` と `requirements_packet.json` の保存を追加する
6. validation と fallback を追加し、失敗時は `degraded` に写す
7. fixture / unit test を追加する
8. README / specification / evaluation を最小更新する

## Tests

### Outline

- Unit:
  - query family から locale 別 query seed が生成される
  - evidence metadata に source_type / source_tier / locale / freshness が残る
  - confidence / bias_note / kill_condition 欠損候補が packet から除外される
- Integration:
  - offline fixture preset で run directory に `kano.json` と `requirements_packet.json` が保存される
  - 既存 preset の artifact 保存が変わらない
- Coverage:
  - 既存 unittest を維持し、追加分は fixture ベースで確認する

## Commands

### Run gates

- `python -m unittest discover tests`
- `python -m rand_research.cli heartbeat --dry-run --max-items 2`
- `python -m rand_research.cli env-check`

## Notes

### Task分割案（未承認）

P0 を次の 3 seed に分割することを提案する。

| Task ID | 内容 | 依存 |
| --- | --- | --- |
| TASK-20260526-01-1 | preset + prompt + pipeline分岐入口（`mode == "kano_requirements"` の最小分岐） | なし |
| TASK-20260526-01-2 | `kano.py` helper + `kano.json` / `requirements_packet.json` artifact 生成 | TASK-20260526-01-1 |
| TASK-20260526-01-3 | tests + validation + docs 整備 | TASK-20260526-01-2 |

分割理由:
- 各 seed を独立 PR として扱える粒度にする
- 先行コード差分の正式採用を段階的にレビューできる
- 失敗時の rollback 範囲を限定する

ユーザー確認後に分割を正式採用する。現状は P0 単一として扱う。

### 先行コード差分のレビュー観点

先行コード差分を正式採用する場合、次をレビューする。

| 観点 | 確認内容 |
| --- | --- |
| preset schema | `kano_requirements_hybrid` / `kano_requirements_offline_eval` が specification 4.2 の必須キーを持つ |
| artifact fields | `kano.json` / `requirements_packet.json` が specification 5.3 / 5.4 の必須 fields を持つ |
| validation | confidence / bias_note / kill_condition 欠損時の packet 昇格除外が実装されている |
| compatibility | 既存 preset の unittest が通る |
| insight_enabled | preset で `insight_enabled: false` が機能し、deterministic path が動く |
| fixture | `tests/fixtures/kano_evidence.json` が evidence metadata schema を満たす |
| lockfile | `uv.lock` の採用が workspace の依存方針と整合する |

### Rationale

KanoMode は単なる分類器ではなく、証拠束から要求定義パケットを作る支援器として実装する。RanD の既存 runtime と artifact layer を使うことで、新規 OSS を増やさずに最小差分で検証できる。

### Risks

- live search の結果揺れで再現性が落ちる
- complaint 偏重で must_be が増えすぎる
- attractive を hard gate にしてしまう
- LLM が証拠不足でも断定する

### Follow-ups

- TASK-20260526-02: packet-to-gate 変換と schema validation の強化
- TASK-20260526-03: docs / examples / offline eval の整備
- TASK-20260526-04: Kestra flow / schedule 追加
