---
intent_id: INT-KANO-001
owner: rand
status: draft
last_reviewed_at: 2026-05-26
next_review_due: 2026-06-09
source:
  - docs/requirements_kano_mode.md
  - docs/requirements_2.md
  - docs/kano_mode_handoff.md
workflow_reference:
  - Agent_tools/workflow-cookbook/docs/spec.md
  - Agent_tools/workflow-cookbook/TASK.codex.md
  - Agent_tools/workflow-cookbook/EVALUATION.md
---

# RanD KanoMode 仕様書

## 1. 目的

本仕様書は、RanD の `research-runtime` に追加する KanoMode のふるまい、入出力、artifact 契約、既存チェーンとの接続、検証観点を定義する。

KanoMode は、狩野モデルそのものではない。正式な狩野モデル調査を代替せず、検索証拠や fixture evidence をもとに Kano 参照の仮分類を行い、実務で使える `requirements_packet.json` を生成する要求定義支援モードである。加えて、既存の要件定義を再評価して `requirements_audit_packet.json` を生成する要件監査モードも扱う。新規 OSS ではなく、RanD の既存 runtime / preset / artifact layer に追加する軽量アダプタとして扱う。

特に一元的品質は、ネット上の比較、改善要求、不満、称賛、乗り換え理由から疑似的に再現する。つまり `performance` は「実測済みの一元的品質」ではなく、「良くなるほど満足が上がり、悪くなるほど不満が増える可能性が高い」という evidence-backed hypothesis である。

## 2. 適用範囲

### 2.1 対象

- `research-runtime` の preset-driven 実行
- KanoMode 用 preset
- KanoMode 用 prompt
- query family / fixture evidence による証拠収集
- evidence cluster 生成
- persona mode による Kano 分類補助
- `kano.json` の生成
- `requirements_packet.json` の生成
- `requirements_audit_packet.json` の生成
- Requirement Definition Gate の判定
- 既存 artifact / status / taskstate / memx / tracker sync との接続
- offline eval と fixture ベースの検証
- `workflow-cookbook` の Task Seed / Acceptance / Evidence への接続

### 2.2 非対象

- 独立した Kano 専用 OSS
- peer repo の破壊的 API 変更
- live web search を必須にした CI / acceptance
- tracker SaaS の本番認証
- UI ダッシュボード
- 要件採択そのものの自動決定

## 3. 想定利用者

| 利用者 | 目的 |
| --- | --- |
| RanD operator | preset を指定して KanoMode を実行し、要求定義 packet を得る |
| Product reviewer | `requirements_packet.json` を読み、採択 / 保留 / 再調査を判断する |
| QA / manual-bb 担当 | packet の acceptance / risk / manual focus からテスト観点を作る |
| Workflow maintainer | Task Seed / Acceptance / Evidence へ落とし、作業を追跡する |
| AI エージェント | 要件、仕様、RUNBOOK、Task Seed から次の作業単位を判断する |

## 4. モード

| mode | 目的 | 主入力 | 主出力 |
| --- | --- | --- | --- |
| `kano_discovery_mode` | 新規要求や調査テーマから要件候補を起こす | topic, query family, fixture evidence, external evidence | `kano.json`, `requirements_packet.json` |
| `kano_audit_mode` | 既存要件定義を監査し、要件定義ゲートへ渡す | existing requirements document, external evidence, implementation evidence | `kano.json`, `requirements_audit_packet.json` |

`kano_discovery_mode` は「何を要求にすべきか」を作る。`kano_audit_mode` は「すでに書かれた要件を信じてよいか」を確認する。

## 5. 機能仕様

### 5.1 実行入口

KanoMode は `run-once` の preset として起動する。

```powershell
cd research-runtime
python -m rand_research.cli run-once --preset kano_requirements_hybrid
python -m rand_research.cli run-once --preset kano_requirements_offline_eval --max-items 5
```

Windows 環境で `python` が Windows Store stub に当たる場合は、既存 README の方針に従い `uv run python` を使う。

```powershell
cd research-runtime
uv run python -m rand_research.cli run-once --preset kano_requirements_offline_eval --max-items 5
```

### 5.2 preset

| preset | 種別 | 目的 | 受け入れでの扱い |
| --- | --- | --- | --- |
| `kano_requirements_hybrid` | live/search-ready | query family から Kano evidence seed を生成し、将来 live search adapter へ接続する | shadow / pilot |
| `kano_requirements_offline_eval` | fixture/cached | fixture evidence だけで artifact 契約を再現検証する | 正本 |
| `kano_requirements_audit` | audit | 既存要件定義を再評価し、`requirements_audit_packet.json` を生成する | pilot |

KanoMode preset は少なくとも次を宣言できる。

- `mode: "kano_requirements"`
- `topic`
- `persona_modes`
- `locales`
- `freshness_window_days`
- `sources`
- `output_profile`
- `gate_enabled`
- `insight_enabled`

offline eval は live web search と live LLM 実行に依存しない。これにより、要件 / 仕様 / artifact 契約の回帰確認を安定させる。

`kano_requirements_hybrid` は `kano_shadow_search` adapter を持つ。adapter は `RAND_KANO_SHADOW_SEARCH=1` のときだけ有効になり、検索 URL から取得した link evidence を `source_tier=user_signal` または `comparison` として保存する。未設定時は 0 件を返し、fixture / query seed の再現性を壊さない。live shadow evidence は検索順位、SEO、locale、時点差のバイアスを持つため、通常 acceptance の正本にはしない。

### 5.3 query family

query family は Kano 参照の品質信号を拾うための検索意図である。狩野モデルの質問票を実施する代わりに、ネット上で自然発生している反応を evidence として集める。

| family | 目的 | 主な Kano 信号 |
| --- | --- | --- |
| `complaints` | 不満、離脱、詰まりを拾う | `must_be`, `reverse` |
| `praise` | 称賛、便利さ、驚きを拾う | `attractive`, `performance` |
| `compare` | 競合比較、乗り換え理由を拾い、一元的品質を疑似再現する | `performance` |
| `expectation` | 当たり前、最低限、must have を拾う | `must_be` |
| `delight` | あるとうれしい、意外に良いを拾う | `attractive` |
| `churn` | 解約、利用停止、後悔を拾う | `must_be`, `reverse` |
| `official` | 公式説明、release note、仕様を拾う | baseline / primary evidence |
| `competitor_baseline` | 競合標準機能を拾う | must-be 化の兆候 |

query family は `locale` と `segment` を metadata に残す。日本語市場と英語圏市場の期待値を混同しないためである。

### 5.4 evidence metadata

KanoMode の evidence は、最低限次を保持する。

| field | 内容 |
| --- | --- |
| `evidence_id` | artifact 内で一意な evidence ID |
| `source_type` | `complaints`, `praise`, `compare`, `official` など |
| `source_tier` | `primary`, `user_signal`, `comparison`, `query_seed`, `fixture` など |
| `source_ref` | URL、fixture URI、query URI |
| `summary` | evidence の要約 |
| `weight` | evidence 重み |
| `freshness_days` | 取得または公開からの日数。未指定なら null |
| `locale` | `ja-JP`, `en-US`, `und` など |

### 5.5 evidence cluster

KanoMode は単一 item ではなく、要求候補 cluster 単位で分類する。

cluster の最低仕様:

- 1 cluster は 1 つの要求候補を表す。
- cluster は 1 件以上の evidence を持つ。
- cluster は `candidate_id` を持つ。
- cluster は `statement` を持つ。
- cluster は evidence refs を保持する。
- cluster は persona votes を保持する。

### 5.6 persona mode

persona mode は、同じ evidence を異なる観点で読むための分類補助である。

| persona | 主な責務 | 主な出力 |
| --- | --- | --- |
| `researcher` | 繰り返し語られる問題と証拠束を見る | cluster, evidence gap, open question |
| `user` | ある / ない場合の満足・不満の非対称性を見る | Kano vote, context, sentiment |
| `gatekeeper` | 過信、release blocker、kill condition を見る | confidence cap, hard / soft gate |
| `product` | 要求文、KPI、acceptance へ落とす | requirement, KPI draft, priority |

persona votes は `kano.json.kano_candidates[*].persona_votes` に保存する。

### 5.7 Kano type

Kano type は狩野モデルの分類語彙を借りた仮分類であり、正式調査の結果ではない。各 type は downstream gate のための作業仮説として扱う。

| type | 意味 | gate policy |
| --- | --- | --- |
| `must_be` | 無いと強い不満が出る最低条件 | `hard_gate` |
| `performance` | ネット上の比較・改善要求・悪化時不満から疑似再現した一元的品質の競争軸 | `threshold_gate` |
| `attractive` | あるとうれしい差別化要素 | `soft_experiment_gate` |
| `indifferent` | 要求化の優先度が低い | `observe_only` |
| `reverse` | あると不満が出る可能性がある | `negative_gate` |
| `questionable` | 証拠品質または分類が怪しい | `do_not_gate` |

`questionable` は `requirements_packet.json` へ昇格しない。

## 6. I/O Contract

### 6.1 Input

| 入力 | 内容 |
| --- | --- |
| preset | `kano_requirements_hybrid` または `kano_requirements_offline_eval` |
| topic | 調査対象の製品 / 機能 / 要件テーマ |
| locales | evidence の対象 locale |
| query_families | Kano 信号別の検索意図 |
| source metadata | source tier, source type, freshness, segment |
| state context | 既知 URL、過去 run、open task、memory entries |
| fixture evidence | offline eval 用の固定 evidence |
| existing requirements document | audit mode で監査する既存要件定義 |
| implementation evidence | code-to-gate へ渡す実装・テスト・リスク証跡 |

### 6.2 Output

KanoMode は既存 8 artifact に加えて、次を追加できる。

- `kano.json`
- `requirements_packet.json`
- `requirements_audit_packet.json`
- `downstream_handoff.json`

既存 8 artifact:

- `report.md`
- `report.json`
- `insight.json`
- `gate.json`
- `meta.json`
- `memx_journal.json`
- `tracker_sync.json`
- `state_context.json`

### 6.3 `kano.json`

`kano.json` は分析台帳である。

必須 root fields:

| field | 内容 |
| --- | --- |
| `schema_version` | artifact schema version |
| `mode` | `kano` |
| `request_id` | Kano run request ID |
| `topic` | 対象テーマ |
| `persona_modes` | 実行した persona mode |
| `source_summary` | evidence 件数と source 内訳 |
| `kano_candidates` | Kano 候補一覧 |
| `known_biases` | 既知バイアス |

`kano_candidates[*]` の必須 fields:

| field | 内容 |
| --- | --- |
| `candidate_id` | `KC-001` 形式の候補 ID |
| `statement` | 要求候補文 |
| `kano_type` | Kano type |
| `confidence` | 確信度 |
| `evidence` | evidence entries |
| `persona_votes` | persona ごとの vote |
| `bias_note` | 想定バイアス |
| `kill_condition` | 何が起きたら捨てるか |

### 6.4 `requirements_packet.json`

`requirements_packet.json` は downstream OSS と人間レビューへ渡す実務契約である。

必須 root fields:

| field | 内容 |
| --- | --- |
| `schema_version` | artifact schema version |
| `packet_id` | packet ID |
| `derived_from` | 原則 `kano.json` |
| `product_context` | 製品、領域、対象 segment、locale |
| `assumptions` | 前提 |
| `requirements` | 要求一覧 |
| `release_readiness_prelude` | release readiness 前段 |

`requirements[*]` の必須 fields:

| field | 内容 |
| --- | --- |
| `requirement_id` | `REQ-001` 形式の要求 ID |
| `title` | 要求タイトル |
| `statement` | 要求文 |
| `kano_type` | Kano type |
| `priority` | P0 / P1 / P2 / P3 |
| `confidence` | 確信度 |
| `evidence_refs` | `KC-*` と `EV-*` の参照 |
| `kpi` | KPI 草案 |
| `acceptance_criteria` | 受け入れ条件 |
| `risks` | リスク |
| `manual_bb_focus` | 手動ブラックボックス観点 |
| `downstream_hooks` | downstream OSS への接続先 |
| `gate_policy` | gate 方針 |
| `bias_note` | 想定バイアス |
| `kill_condition` | 何が起きたら捨てるか |

### 6.5 `requirements_audit_packet.json`

`requirements_audit_packet.json` は既存要件定義の監査結果である。

Sample artifact: [examples/requirements_audit_packet.sample.json](examples/requirements_audit_packet.sample.json)

必須 root fields:

| field | 内容 |
| --- | --- |
| `schema_version` | artifact schema version |
| `document_id` | 監査対象の要件定義 ID |
| `summary` | 監査要約 |
| `requirements` | 要件ごとの監査結果 |
| `gate_summary` | Requirement Definition Gate の集計 |
| `source_refs` | 監査に使った要件・証拠・実装参照 |
| `assumptions` | 前提 |

`requirements[*]` の必須 fields:

| field | 内容 |
| --- | --- |
| `requirement_id` | 既存要件 ID |
| `original_text` | 監査対象の原文 |
| `kano_estimate` | Kano 再分類 |
| `confidence` | 確信度 |
| `evidence` | 外部証跡・内部証跡 |
| `testability` | `high`, `medium`, `low`, `blocked` |
| `implementation_alignment` | `high`, `medium`, `low`, `unknown` |
| `risks` | 残リスク |
| `issues` | 問題点 |
| `suggested_action` | 推奨アクション |
| `gate_verdict` | `go`, `conditional_go`, `no_go` |

### 6.6 `downstream_handoff.json`

`downstream_handoff.json` は、KanoMode の主契約を downstream OSS が消費しやすい形へ分解する dry-run artifact である。

必須 root fields:

| field | 内容 |
| --- | --- |
| `schema_version` | artifact schema version |
| `handoff_id` | handoff ID |
| `mode` | `requirements_packet` または `requirements_audit_packet` |
| `workflow_cookbook` | Task Seed 候補 |
| `manual_bb_test_harness` | 手動 BB 観点 seed |
| `code_to_gate` | phase contract / implementation alignment seed |
| `tracker_bridge` | tracker dry-run issue |
| `status` | `dry_run` |
| `error` | エラー。正常時は null |

補助 CLI:

| command | 内容 |
| --- | --- |
| `shadow-eval-template` | `kano.json` から live/search shadow evidence の人手評価 JSON/CSV を生成する |
| `tracker-review` | `downstream_handoff.json` または `tracker_sync.json` の dry-run issue をレビュー台帳へ変換する |
| `generate-task-seeds` | `downstream_handoff.json` から Task Seed draft を生成する。既定は dry-run で、`--write` 時だけファイルを書く |

### 6.7 昇格ルール

Kano candidate は、次を満たす場合だけ `requirements_packet.json` へ昇格できる。

- `confidence` が存在する。
- `bias_note` が空でない。
- `kill_condition` が空でない。
- `kano_type` が `questionable` ではない。
- evidence refs が 1 件以上ある。

`must_be` へ昇格する場合は、少なくとも user signal または primary source の evidence を持つことを推奨する。

## 7. Requirement Definition Gate

Requirement Definition Gate は、既存要件定義を「書いてあるから正しい」と扱わず、次の軸で判定する。

| 軸 | 見ること | 主担当 |
| --- | --- | --- |
| 価値妥当性 | must-be / performance / attractive / reverse の仮分類が妥当か | RanD KanoMode |
| ユーザー期待整合 | 外部証跡や競合 baseline とズレていないか | RanD KanoMode |
| 検収可能性 | 受入条件が観測可能か。手動 BB で確認できるか | manual-bb-test-harness |
| 実装整合性 | 実装・構造・テストが要件を支えているか | code-to-gate |
| 残リスク | Go 判断に残すべきリスクが明示されているか | 全体 |

判定基準:

| verdict | 条件 |
| --- | --- |
| `go` | must-be の抜けが少なく、受入条件と KPI が観測可能で、実装整合に大きな破綻がない |
| `conditional_go` | 方向性は妥当だが、受入条件、KPI、根拠、実装リスクの補強が必要 |
| `no_go` | must-be 抜け、attractive の must-be 誤扱い、価値根拠不足、検収不能、実装負債過大のいずれかがある |

## 8. 既存チェーンとの接続

KanoMode も RanD の正規チェーンに従う。

```text
research -> insight -> gate -> sync -> notify
```

ただし MVP / offline eval では、deterministic な evidence-to-packet 変換を優先し、live LLM insight を必須にしない。

| stage | KanoMode での扱い |
| --- | --- |
| research | query seed / fixture evidence を収集する |
| insight | persona-aware insight または deterministic fallback で候補を整理する |
| gate | packet-to-gate 変換により hard / soft / threshold を分ける |
| sync | `requirements_packet.json` の参照を tracker / taskstate / memx へ残す |
| notify | run summary と artifact path を通知対象にする |

## 9. Downstream 連携

| 連携先 | 渡すもの | 期待する使い方 |
| --- | --- | --- |
| workflow-cookbook | requirements packet, evidence refs, KPI | Task Seed / Acceptance / Evidence |
| manual-bb-test-harness | requirement, acceptance, risk, manual_bb_focus | feature spec / test model / manual cases |
| code-to-gate | phase contract, risk, acceptance | readiness / risk-register / test-seeds |
| shipyard-cp | requirements packet | plan stage input |
| experiment-gate | GateRequest 相当 | go / hold / no_go 判断 |

downstream への主契約は `requirements_packet.json` に集約する。

audit mode では downstream への主契約を `requirements_audit_packet.json` にする。`manual-bb-test-harness` は `testability` と `manual_bb_focus` を使い、`code-to-gate` は `implementation_alignment` と `risks` を使う。

## 10. 互換性と変更管理

- 既存 preset の挙動を破壊してはならない。
- 既存 8 artifact の required fields を削除してはならない。
- KanoMode artifact は additive change として追加する。
- `schema_version` は root に必ず置く。
- field 追加は minor 相当として扱う。
- required field の削除、field 意味変更、Kano type / gate policy の意味変更は major 相当として扱う。
- live web search の不安定性を CI の必須条件にしてはならない。
- 先行コード差分は [kano_mode_handoff.md](kano_mode_handoff.md) の扱いに従う。

## 11. エラーと status

| 事象 | 推奨 status | 理由 |
| --- | --- | --- |
| source 全滅 | `failed` | research 入力がない |
| fixture 読み込み失敗 | `failed` | offline eval の正本が壊れている |
| 一部 source 失敗 | `degraded` | 部分 evidence で続行可能 |
| live insight 失敗 | `degraded` | fallback / deterministic path がある |
| packet validation 失敗 | `degraded` または `failed` | packet 生成不能なら `failed` |
| report 保存失敗 | `failed` | artifact 契約を満たせない |

offline eval では、live insight / live search の不在で status が揺れないようにする。

## 12. 検証観点

### 12.1 文書整合

- [requirements_kano_mode.md](requirements_kano_mode.md) と本仕様の FR / AC / artifact fields が矛盾しない。
- [evaluation.md](evaluation.md) の AC-K が本仕様の acceptance と一致する。
- [RUNBOOK.md](../RUNBOOK.md) から本仕様、要件、Task Seed、引継ぎ資料へ辿れる。

### 12.2 Artifact 検証

- `kano.json` が必須 root fields を持つ。
- `kano_candidates[*]` が必須 fields を持つ。
- `requirements_packet.json` が必須 root fields を持つ。
- `requirements[*]` が必須 fields を持つ。
- `confidence`, `bias_note`, `kill_condition` 欠損 candidate が packet 昇格しない。
- `requirements_audit_packet.json` が必須 root fields を持つ。
- `requirements_audit_packet.json.requirements[*]` が `testability`, `implementation_alignment`, `gate_verdict` を持つ。

### 12.3 Runtime 検証

代表コマンド:

```powershell
cd research-runtime
uv run python -m unittest discover tests
uv run python -m rand_research.cli run-once --preset kano_requirements_offline_eval --max-items 5
```

期待結果:

- unittest が通る。
- offline eval が live web search なしで完了する。
- `report.json.artifacts.kano_json` が存在する。
- `report.json.artifacts.requirements_packet_json` が存在する。
- `requirements_packet.requirements` に昇格済み要求が含まれる。

### 12.4 Drift 検知

次のいずれかが起きたら、本仕様を更新する。

- `kano.json` の field が増減した。
- `requirements_packet.json` の field が増減した。
- Kano type が増減した。
- gate policy の意味が変わった。
- preset 名が変わった。
- offline eval の fixture 契約が変わった。
- downstream hook の名前が変わった。
- `requirements_audit_packet.json` の field が増減した。
- Requirement Definition Gate の判定基準が変わった。

## 13. Task / Acceptance / Evidence

Task Seed:

- [tasks/TASK-20260526-01-kano-mode-p0.md](tasks/TASK-20260526-01-kano-mode-p0.md)
- [tasks/TASK-20260526-05-kano-audit-mode.md](tasks/TASK-20260526-05-kano-audit-mode.md)

Acceptance:

- pilot段階では `workflow-cookbook/docs/acceptance/README.md` 参照に留める。
- 正式運用開始後、RanD側に `docs/acceptance/AC-YYYYMMDD-xx.md` を作成し、`AC-YYYYMMDD-xx.md` 形式に従う。
- 検収記録は `docs/evaluation.md` AC-K 系で代替可能。

Evidence:

- 検証証跡は [kano_mode_handoff.md](kano_mode_handoff.md) に記録済み。
- 正式 PR 化する場合は、PR 本文から Task Seed / Acceptance / Evidence へリンクする。

## 14. 関連資料

- 要件: [requirements_kano_mode.md](requirements_kano_mode.md)
- 親要件: [requirements.md](requirements.md)
- 親仕様: [specification.md](specification.md)
- 検収: [evaluation.md](evaluation.md)
- RUNBOOK: [../RUNBOOK.md](../RUNBOOK.md)
- 引継ぎ: [kano_mode_handoff.md](kano_mode_handoff.md)
- Task Seed: [tasks/TASK-20260526-01-kano-mode-p0.md](tasks/TASK-20260526-01-kano-mode-p0.md)
