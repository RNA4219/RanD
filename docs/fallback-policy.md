# Fallback ポリシー

## 目的

RanD が live API、外部ツール、LLM 呼び出し、peer repository、optional component の障害時にどう振る舞うかを定義する。RanD は silent success ではなく graceful degradation を優先し、primary path と fallback path を明確に区別する。

## 正規実行ステータス

| status | 意味 |
| --- | --- |
| `ok` | primary path が完了し、必須 artifact が生成された |
| `degraded` | fallback path は完了したが、品質、freshness、coverage、confidence のいずれかが低下した |
| `failed` | 利用可能な artifact を生成できなかった |
| `skipped` | 明示的な理由を記録して、意図的に実行しなかった |
| `needs_review` | downstream 利用前に人間レビューが必要である |

`degraded` は実行結果、`needs_review` はレビュー要否を表す。実装上ひとつの status field しか持てない場合、最終判断へ進む artifact は `needs_review` を優先し、元の実行状態を別 field に保持する。

## Fallback 順序

1. primary component または live path
2. peer repository API または local adapter
3. cached artifact または fixture
4. deterministic local fallback
5. `failed` または `needs_review` として記録

利用できない段階は理由を記録して次へ進む。契約不一致や安全上の問題がある段階を無理に利用してはならない。

## 運用ルール

- fallback は primary result を装ってはならない。
- fallback artifact は `fallback_from`、`fallback_to`、`reason`、`lost_capabilities`、`review_required` を必須とする。
- live LLM または web fetch が失敗しても、fixture が利用可能なら決定論的 validation を継続できる。
- `degraded` な出力は planning や exploration には利用できるが、人間レビューなしに final acceptance、release、`go`、`pass`、`approve` を決定してはならない。
- evidence freshness が重要な場合、stale な cached artifact は `degraded` または `needs_review` とする。
- fallback により coverage を失う場合、対象外になった source、期間、検証、capability を artifact に明記する。
- 必須 field が欠けた artifact や schema contract に適合しない artifact は、暗黙に受理せず `failed` または `needs_review` とする。
- fallback で生成する artifact も [Artifact Contract Policy](artifact-contract-policy.md) に従う。

## Fallback record 例

```yaml
id: fallback-20260607-001
type: fallback_record
schema_version: "1.0"
producer: rand-research
producer_version: "0.2.0"
created_at: "2026-06-07T10:30:00+09:00"
status: degraded
fallback_from: external_llm_api
fallback_to: deterministic_local_fallback
reason: api_timeout
lost_capabilities:
  - semantic_reranking
  - live_model_reasoning
review_required: true
downstream_allowed_uses:
  - planning
  - exploration
```

## 障害別の扱い

| 状況 | Fallback と記録 |
| --- | --- |
| LLM unavailable | peer API、fixture、deterministic fallback の順で試し、LLM 固有の推論能力喪失を記録して `degraded` / `needs_review` とする |
| live fetch unavailable | cached artifact または fixture を利用し、freshness と未取得 source を記録する |
| peer repo schema changed | contract validation を失敗させ、互換 adapter がなければ `failed` または `needs_review` とする |
| notification sync failed | core artifact を保持し、同期結果を `failed` として再送可能にする。通知成功を装わない |
| cached fixture used instead of live research | fixture の取得時点、対象範囲、失われた freshness を記録し、最終判断にはレビューを要求する |
