---
intent_id: INT-KANO-001
owner: rand
status: active
last_reviewed_at: 2026-05-26
next_review_due: 2026-06-09
---

# KanoMode Next Steps

## 1. 目的

KanoMode の discovery / audit 両モードについて、実装済みの fixture-based gate から live/search pilot と downstream handoff pilot へ進むための判断、採用条件、未解決事項を整理する。

この文書は現状整理であり、live 検索や tracker 実送信を通常検収の正本にしない。`research-runtime/src/**` を変更する場合は、fixture / unit test で再現性を維持する。

## 2. 現在地

| 領域 | 状態 | 正本 |
| --- | --- | --- |
| discovery mode 要件 | 作成済み | [requirements_kano_mode.md](requirements_kano_mode.md) |
| discovery mode 仕様 | 作成済み | [specification_kano_mode.md](specification_kano_mode.md) |
| discovery mode 実装 | 実装済み | `kano_requirements_hybrid`, `kano_requirements_offline_eval` |
| audit mode 要件 | 作成済み | [requirements_kano_mode.md](requirements_kano_mode.md) |
| audit mode 仕様 | 作成済み | [specification_kano_mode.md](specification_kano_mode.md) |
| audit mode 実装 | 実装済み | `kano_requirements_audit`, `tests/fixtures/audit_evidence.json` |
| shadow search | 実装済み。既定無効 | `kano_shadow_search`, `RAND_KANO_SHADOW_SEARCH` |
| downstream handoff | 実装済み。dry-run artifact | `downstream_handoff.json` |

## 3. 契約の分離

### 3.1 Discovery Mode

Discovery mode は新規要求や調査テーマから要件候補を起こす。

主契約:

- `kano.json`
- `requirements_packet.json`

下流連携:

- `workflow-cookbook`: Task Seed / Acceptance / Evidence
- `manual-bb-test-harness`: feature spec / manual test model
- `code-to-gate`: readiness / risk / test seed
- `shipyard-cp`: plan input

### 3.2 Audit Mode

Audit mode は既存要件定義を監査する。

主契約:

- `kano.json`
- `requirements_audit_packet.json`

下流連携:

- `manual-bb-test-harness`: testability / manual_bb_focus / residual risk
- `code-to-gate`: implementation_alignment / risk / release readiness
- `workflow-cookbook`: audit Task Seed / Evidence / Acceptance

## 4. Pilot へ進む前の判断表

| 判断 | 推奨 | 理由 |
| --- | --- | --- |
| live/search shadow を pilot で有効化するか | 条件付き Go | `RAND_KANO_SHADOW_SEARCH=1` の明示時だけ有効化し、fixture gate と分離する |
| live evidence を requirements 昇格へ使うか | 保留 | 人手 precision 評価なしでは検索ノイズが混ざる |
| tracker dry-run issue を実送信へ進めるか | 保留 | tracker SaaS 認証は out of scope。まず dry-run payload をレビューする |
| downstream handoff を Task Seed ファイル生成へ進めるか | 条件付き Go | `generate-task-seeds` は既定 dry-run。`--write` の前に内容を確認する |
| operations outbox を Misskey 実送信へ接続するか | 条件付き Go | heartbeat flow は operations summary を notifier webhook へ渡す。実送信判断は pulse-kestra 側で行う |

## 5. 文書だけで進めてよい作業

- `shadow-eval-template` の出力を使った人手評価シート運用
- `tracker-review` の出力を使った dry-run issue payload レビュー
- downstream handoff の採択 / 不採択ログ様式整理
- operations state の運用手順追記

## 6. ユーザー確認が必要な作業

- live search を常時有効化すること
- notification outbox を Misskey 実送信へ接続すること
- tracker dry-run issue を実 tracker へ送信すること
- downstream handoff から repo 内 Task Seed ファイルを自動生成すること
- `uv.lock` の採用方針を変えること

## 7. 次の推奨順

1. `kano_requirements_offline_eval` / `kano_requirements_audit` を通常 gate として維持する。
2. `RAND_KANO_SHADOW_SEARCH=1` で少数テーマの shadow run を行い、`shadow-eval-template` で evidence precision を人手評価する。
3. `tracker-review` で dry-run issue を `ready / hold / reject` 観点で確認する。
4. `generate-task-seeds` の dry-run 出力を確認し、必要なものだけ `--write` で draft 化する。
5. `metrics`, `resend-pending`, `replay-plan` の出力を pulse-kestra 側の `operations_summary.json` と照合する。
6. 実送信や自動ファイル生成に進む場合は、別 Task Seed と Acceptance Record を作る。
