# Artifact Contract ポリシー

## 目的

RanD のコンポーネント境界では、暗黙の tool state や非構造な会話ではなく、検査可能な artifact を交換する。artifact は local-first で保存・検証でき、由来、制約、許可用途、判断根拠を監査できる必要がある。

## 必須フィールド

| field | 要件 |
| --- | --- |
| `id` | artifact を一意に識別する |
| `type` | artifact type を示す |
| `schema_version` | contract version を示す |
| producer | nameとversionを持つ生成元object |
| `created_at` | timestamp を timezone 付きで記録する |
| `input_refs` | 入力 artifact や要求への参照を記録する |
| `source_refs` | 根拠となる source を記録する |
| `status` | `ok`、`degraded`、`failed`、`skipped`、`needs_review` のいずれかを記録する |
| `confidence` | 推定や非決定論的出力の場合に記録する |
| `assumptions` | 判断に用いた仮定を記録する |
| `limitations` | coverage、freshness、既知制約を記録する |
| `review_required` | downstream 利用前の人間レビュー要否を記録する |
| `downstream_allowed_uses` | 許可される利用目的を列挙する |
| `checksum` | integrity 確認が必要な場合に記録する |

## 契約ルール
schema 2.0の機械可読な正本はresearch-runtime package同梱のJSON Schema Draft 2020-12とする。schema 1.0はwarning付き読込互換に限定し、live利用を許可しない。


- breaking schema change には新しい `schema_version` を割り当てる。
- downstream consumer は利用前に必須 field と対応 schema version を検証する。
- 必須 field が欠ける場合は silent success にせず、`needs_review` または `failed` とする。
- [Component Trust Policy](component-trust-policy.md) の Level 3 / 4 コンポーネントの出力は、core workflow へ入る前にこの契約へ正規化する。
- gate decision に利用する artifact は、判断を replay または audit できるだけの入力参照、根拠、規則、制約を保持する。
- operations state は artifact 保存後の通知・再送・replay 計画を扱う local outbox であり、run / task の正本である `agent-taskstate` と混同しない。
- 人間の判断も、コメントや chat message だけに残さず `decision_record` として保存する。
- fallback artifact は [Fallback Policy](fallback-policy.md) の fallback field と review 要件も満たす。
- `downstream_allowed_uses` にない用途へ利用する場合は、新たなレビューまたは契約更新を必要とする。

## RanD で扱う代表的な artifact type

- `research_packet`: 調査 source、正規化結果、coverage を保持する
- `insight_record`: 洞察、根拠、confidence、limitations を保持する
- `experiment_gate_result`: gate 規則、入力 evidence、判定、レビュー要否を保持する
- `requirements_packet`: 要求候補、KPI、acceptance、risk、downstream hook を保持する
- `decision_record`: 人間または承認済み gate の判断と理由を保持する
- `task_state_snapshot`: task、run、state の時点情報を保持する
- `pilot_snapshot`: pilot readiness、outbox remediation、metrics の時点証跡を保持する
- `pilot_review`: pilot snapshot に対する運用判断、理由、follow-up を保持する
- `fallback_record`: fallback 経路、理由、失われた capability を保持する
- `external_sync_result`: tracker、notification など外部同期の結果を保持する

## 最小 JSON 例

```json
{
  "id": "insight-20260607-001",
  "type": "insight_record",
  "schema_version": "2.0",
  "producer": {"name": "RanD", "version": "0.3.0"},
  "created_at": "2026-06-07T10:30:00+09:00",
  "input_refs": ["research-packet-20260607-001"],
  "source_refs": ["https://example.com/source"],
  "status": "needs_review",
  "confidence": 0.72,
  "assumptions": ["source metadata is accurate"],
  "limitations": ["single-source evidence"],
  "review_required": true,
  "downstream_allowed_uses": ["planning", "experiment_design"],
  "checksum": "sha256:example"
}
```

## 周辺リポジトリとの概念的な接続

このポリシーは周辺リポジトリへの hard dependency を作らず、artifact を介して概念的に接続する。

- `agent-taskstate`: `task_state_snapshot`、run、decision の参照形式と状態引継ぎ先
- `workflow-cookbook`: Task Seed、Acceptance、Evidence、Guardrails へ渡す入力契約
- `quality-evidence-graph`: artifact と evidence の由来、関係、coverage を追跡する接続候補
- `code-to-gate`: requirements、risk、test evidence、release readiness を gate 入力へ変換する接続候補

各連携は adapter または export/import で実現できる。周辺リポジトリが利用できない場合も、RanD 内の artifact は単独で検査、保存、レビューできなければならない。
