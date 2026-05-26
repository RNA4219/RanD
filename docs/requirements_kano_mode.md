---
intent_id: INT-KANO-001
owner: rand
status: draft
last_reviewed_at: 2026-05-26
next_review_due: 2026-06-09
source:
  - docs/requirements_2.md
  - docs/requirements.md
  - docs/specification.md
  - docs/specification_kano_mode.md
workflow_reference:
  - Agent_tools/workflow-cookbook/HUB.codex.md
  - Agent_tools/workflow-cookbook/TASK.codex.md
  - Agent_tools/workflow-cookbook/EVALUATION.md
---

# RanD KanoMode 要件定義

## 1. 目的

RanD に KanoMode を追加し、既存の `research -> insight -> gate -> sync -> notify` の正規チェーンを壊さずに、検索証拠から Kano 参照の仮分類と要求定義パケットを生成できるようにする。

ここでいう KanoMode は、狩野モデルそのものを実施するものではない。機能的質問 / 非機能的質問による正式な狩野モデル調査ではなく、ネット上の不満、称賛、比較、期待、離脱理由、公式情報を evidence として集め、要求候補が「当たり前品質」「一元的品質」「魅力品質」「逆品質」などのどれに近いかを推定する要求分析アダプタである。

特に一元的品質は、ネットを介して疑似的に再現する。競合比較、速度、精度、手間、価格、安定性などに対する反応を集め、「良いほど満足が上がり、悪いほど不満が増える」傾きがあるかを仮説化する。したがって出力は最終判定ではなく、人間レビュー、Acceptance、Evidence、下流 gate に渡すための仮説付き packet として扱う。

本要件定義の目的は、調査レポートである [requirements_2.md](requirements_2.md) を実装可能な契約へ圧縮し、`workflow-cookbook` の Task Seed / Acceptance / Evidence 運用に載せることである。

KanoMode は次の 2 モードを持つ。

- `kano_discovery_mode`: 新規要求や調査テーマから要件候補を起こす。
- `kano_audit_mode`: 既存の要件定義を監査し、価値妥当性、検収可能性、実装整合性のゲートへ渡す。

## 2. 問題定義

現在の RanD は、preset に基づく research runtime、`insight-agent` 連携、`experiment-gate` 連携、artifact 保存を持つ。一方で、KanoMode に必要な次の契約はまだ存在しない。

- complaint / praise / compare / expectation など、Kano 参照の品質信号を拾う検索クエリ駆動の証拠収集
- 単一 item ではなく、要求候補クラスタ単位で insight を実行する処理
- researcher / user / gatekeeper / product の persona 切替
- `kano.json` と `requirements_packet.json` の artifact 契約
- requirements packet を `experiment-gate` へ写像する packet gate 変換
- 既存要件定義を入力にして `requirements_audit_packet.json` を生成する監査契約
- manual-bb-test-harness / code-to-gate へ渡す Requirement Definition Gate 契約

KanoMode は新規 OSS ではなく、RanD の research runtime に追加する軽量アダプタとして扱う。

## 3. スコープ

### 3.1 In Scope

- `research-runtime` の preset-driven な KanoMode 実行
- Kano 向け prompt と persona mode の定義
- 検索クエリ型 fetcher または既存 search adapter への薄い接続
- evidence cluster を入力とする persona-aware insight payload
- `kano.json` と `requirements_packet.json` の保存
- `requirements_audit_packet.json` の保存
- requirements packet から `experiment-gate` への GateRequest 変換
- requirements audit packet から manual-bb-test-harness / code-to-gate へ渡す監査導線
- fixture / cached corpus を使う offline eval
- `workflow-cookbook` の Task Seed / Acceptance / Evidence に沿った検証記録

### 3.2 Out of Scope

- 独立した Kano 専用 OSS の新設
- peer repo 側の API 破壊的変更
- tracker SaaS 側の認証や本番同期設計
- UI ダッシュボード
- live web search 結果だけを正本にする受け入れ判定

## 4. I/O Contract

### 4.1 Input

- preset: `research-runtime/configs/presets/kano_requirements_hybrid.json`
- source seed:
  - topic
  - target product / segment
  - locale
  - query family
  - freshness window
  - domain allow / deny
- existing RanD context:
  - `state_context`
  - `memx` read history
  - previous run artifacts

### 4.2 Output

- `kano.json`
  - Kano 分析台帳
  - evidence cluster
  - persona votes
  - confidence
  - bias note
  - kill condition
- `requirements_packet.json`
  - 実務向け要求定義パケット
  - requirement / KPI / acceptance / risk
  - downstream hooks
  - release readiness prelude
- `requirements_audit_packet.json`
  - 既存要件定義の監査パケット
  - requirement ごとの Kano 再分類
  - testability
  - implementation alignment
  - issues
  - suggested action
  - requirement gate verdict
- 既存 artifact
  - `report.json`
  - `insight.json`
  - `gate.json`
  - `meta.json`
  - `state_context.json`
  - `memx_journal.json`
  - `tracker_sync.json`

すべての新規 JSON artifact は `schema_version` を必須とする。

## 5. 機能要求

| ID | 要求 | 測定条件 |
| --- | --- | --- |
| FR-K01 | KanoMode は preset から起動できること | `run-once --preset kano_requirements_hybrid` が受け付けられる |
| FR-K02 | preset は query family, persona modes, artifact policy を宣言できること | preset JSON に該当キーが存在する |
| FR-K03 | query family は complaints, praise, compare, expectation, delight, churn, official, competitor_baseline を扱えること | fixture または unit test で query expansion を確認できる |
| FR-K04 | evidence は source tier, source type, locale, freshness を metadata として保持すること | `kano.json` の evidence entries で確認できる |
| FR-K05 | 複数 evidence を要求候補クラスタへまとめられること | cluster ID と evidence refs が保存される |
| FR-K06 | persona mode は researcher, user, gatekeeper, product を扱えること | `kano.json.persona_modes` と persona votes で確認できる |
| FR-K07 | Kano type は must_be, performance, attractive, indifferent, reverse, questionable を扱えること | schema / test / sample artifact で確認できる |
| FR-K18 | `performance` は一元的品質そのものの実測ではなく、比較・改善幅・悪化時不満などのネット証跡から疑似再現した仮分類として扱うこと | requirements / specification / README に明記されている |
| FR-K08 | `requirements_packet.json` は requirement, KPI, acceptance, risk, downstream hook を含むこと | sample artifact と schema test で確認できる |
| FR-K09 | must_be は hard gate、performance は threshold gate、attractive は soft / experiment gate に写像できること | packet-to-gate 変換 test で確認できる |
| FR-K10 | confidence, bias_note, kill_condition が欠ける候補は packet 昇格しないこと | validation test で確認できる |
| FR-K11 | live search が失敗しても offline eval preset で再現可能に検証できること | `kano_requirements_offline_eval` が fixture 入力で動く |
| FR-K12 | 既存の `report.json.status` は KanoMode の部分失敗を `degraded` として表現できること | integration test で確認できる |
| FR-K13 | KanoMode は discovery と audit の 2 モードを区別できること | preset または mode field で `kano_discovery_mode` / `kano_audit_mode` が判別できる |
| FR-K14 | 既存要件定義を audit input として読み、requirement ごとの Kano 再評価を出せること | `requirements_audit_packet.json.requirements[*].kano_estimate` で確認できる |
| FR-K15 | audit packet は testability と implementation_alignment を持つこと | `requirements_audit_packet.json.requirements[*]` で確認できる |
| FR-K16 | audit packet は manual-bb-test-harness と code-to-gate へ渡す gate summary を持つこと | `requirements_audit_packet.json.gate_summary` で確認できる |
| FR-K17 | Requirement Definition Gate は `go`, `conditional_go`, `no_go` を返せること | audit fixture または sample artifact で確認できる |

## 6. 非機能要求

| ID | 要求 | 測定条件 |
| --- | --- | --- |
| NFR-K01 | 既存 preset / CLI / artifact の後方互換を壊さないこと | 既存 unittest が通る |
| NFR-K02 | live web search を通常受け入れの必須条件にしないこと | offline eval と fixture test が存在する |
| NFR-K03 | LLM の断定を避けるため、confidence / bias / kill condition を必須化すること | schema validation で確認できる |
| NFR-K04 | 日本語と英語の locale を evidence metadata で分離できること | sample artifact で `locale` が確認できる |
| NFR-K05 | 新規依存は最小化し、既存 adapter / runtime pattern を優先すること | PR diff と docs で確認できる |
| NFR-K06 | discovery mode で downstream OSS へ渡す主契約は `requirements_packet.json` に集約すること | README / specification に明記される |
| NFR-K07 | 既存要件監査では、書かれた要件を正とせず外部証跡・Kano分類・検収可能性・実装整合性で再評価すること | audit specification と gate criteria に明記される |
| NFR-K08 | audit mode で downstream OSS へ渡す主契約は `requirements_audit_packet.json` に集約すること | specification に明記される |

## 7. 成功指標

| 指標 | 目的 | 目標 |
| --- | --- | --- |
| `requirements_packet_accept_rate` | レビューで採択された要求比率を見る | pilot で 0.70 以上 |
| `evidence_precision_at_5` | 上位 evidence が要求を支えているかを見る | 人手評価で 0.80 以上 |
| `must_be_false_positive_rate` | must_be 過剰分類を抑える | pilot で 0.20 以下 |
| `packet_schema_valid_rate` | downstream 消費可能性を見る | 1.00 |
| `manual_bb_gap_count` | 要求から手動 BB 観点へ落ちる抜けを見る | pilot ごとに記録し、増減を追跡 |
| `requirement_gate_conditional_rate` | 既存要件定義で Conditional Go になった比率を見る | pilot ごとに記録 |
| `audit_issue_resolution_rate` | audit で見つかった issue が修正された比率を見る | 0.70 以上 |

## 8. 受け入れ条件

| ID | 条件 | 判定方法 |
| --- | --- | --- |
| AC-K01 | `kano_requirements_hybrid` preset が追加されている | preset JSON を確認 |
| AC-K02 | KanoMode の query family が fixture で検証されている | fetcher / query expansion test |
| AC-K03 | persona-aware insight payload が cluster 単位で生成される | unit test または sample artifact |
| AC-K04 | `kano.json` が `schema_version`, `kano_candidates`, `evidence`, `persona_votes` を持つ | schema / fixture validation |
| AC-K05 | `requirements_packet.json` が requirements, KPI, acceptance, risks, downstream_hooks を持つ | schema / fixture validation |
| AC-K06 | confidence, bias_note, kill_condition 欠損時に packet 昇格しない | validation test |
| AC-K07 | packet-to-gate 変換で must_be / performance / attractive の gate policy が分かれる | conversion test |
| AC-K08 | 既存 preset の unittest が壊れていない | `python -m unittest discover tests` |
| AC-K09 | live web なしで offline eval が実行できる | offline preset または fixture test |
| AC-K10 | README / specification / evaluation に KanoMode の artifact 契約が追記されている | docs review |

### Audit Mode 受け入れ条件

Audit mode の受け入れ条件は [evaluation.md](evaluation.md) の AC-K07 ~ AC-K09 を参照。

| ID | 条件 | 正本 |
| --- | --- | --- |
| AC-K07 | `requirements_audit_packet.json` の root と requirement item の必須 field が仕様化されている | [evaluation.md AC-K07](evaluation.md) |
| AC-K08 | Requirement Definition Gate が `go`, `conditional_go`, `no_go` の判定基準を持つ | [evaluation.md AC-K08](evaluation.md) |
| AC-K09 | manual-bb-test-harness と code-to-gate の役割分担が仕様化されている | [evaluation.md AC-K09](evaluation.md) |

## 9. 実装 Task Seed

| Task | 優先度 | 目的 | 依存 |
| --- | --- | --- | --- |
| [TASK-20260526-01](tasks/TASK-20260526-01-kano-mode-p0.md) | P0 | KanoMode MVP の実装入口を作る | なし |
| TASK-20260526-02 | P1 | packet-to-gate と schema validation を固める | TASK-20260526-01 |
| TASK-20260526-03 | P1 | docs / examples / offline eval を整備する | TASK-20260526-01 |
| TASK-20260526-04 | P2 | Kestra flow / schedule へ展開する | TASK-20260526-02 |
| [TASK-20260526-05](tasks/TASK-20260526-05-kano-audit-mode.md) | P1 | 既存要件監査モードと Requirement Definition Gate を定義する | TASK-20260526-01 |

## 10. リスクと緩和策

| リスク | 症状 | 緩和策 |
| --- | --- | --- |
| complaint bias | must_be が過剰に増える | primary source と user signal を混在させ、confidence 上限を設ける |
| praise illusion | attractive が乱立する | adoption / repeat evidence が弱い場合は P2 以下にする |
| context missing | レビュー断片から誤分類する | bias_note と kill_condition を必須化する |
| temporal drift | 古い delighter を現在も attractive 扱いする | freshness weighting と time slicing を入れる |
| gate overreach | attractive が hard gate になる | gate policy を Kano type から明示計算する |
| live dependency drift | 検索結果で CI が不安定になる | offline eval を正本にし、live は shadow eval とする |

## 11. 検証コマンド

```powershell
cd research-runtime
python -m unittest discover tests
python -m rand_research.cli run-once --preset kano_requirements_offline_eval --max-items 5
python -m rand_research.cli env-check
```

`kano_requirements_offline_eval` は `tests/fixtures/kano_evidence.json` を使うため、live web search なしで artifact 契約を確認できる。
