---
intent_id: INT-KANO-001
owner: rand
status: active
last_reviewed_at: 2026-05-26
next_review_due: 2026-06-09
---

# KanoMode Next Steps

## 1. 目的

KanoMode の discovery / audit 両モードについて、コード実装へ進む前に必要な文書上の判断、採用条件、未解決事項を整理する。

この文書は実装指示ではない。`research-runtime/src/**`、preset、prompt、test、lockfile はユーザー確認なしに変更しない。

## 2. 現在地

| 領域 | 状態 | 正本 |
| --- | --- | --- |
| discovery mode 要件 | 作成済み | [requirements_kano_mode.md](requirements_kano_mode.md) |
| discovery mode 仕様 | 作成済み | [specification_kano_mode.md](specification_kano_mode.md) |
| discovery mode 先行コード差分 | 証跡として存在。正式採用未判断 | [kano_mode_handoff.md](kano_mode_handoff.md) |
| audit mode 要件 | 作成済み | [requirements_kano_mode.md](requirements_kano_mode.md) |
| audit mode 仕様 | 作成済み | [specification_kano_mode.md](specification_kano_mode.md) |
| audit mode sample | 仕様理解用 sample 作成済み。実装 fixture ではない | [examples/requirements_audit_packet.sample.json](examples/requirements_audit_packet.sample.json) |
| audit mode 実装 | 未着手 | [tasks/TASK-20260526-05-kano-audit-mode.md](tasks/TASK-20260526-05-kano-audit-mode.md) |

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

## 4. 実装へ進む前の判断表

| 判断 | 推奨 | 理由 |
| --- | --- | --- |
| discovery mode 先行コード差分を正式採用するか | 保留 | まず先行差分レビュー観点で確認する |
| `uv.lock` を採用するか | 保留 | Windows `tzdata` 対応のため生成されたが、repo 方針確認が必要 |
| audit sample を実装 fixture に昇格するか | 保留 | 現在は仕様理解用 sample。fixture 化には schema / test 方針が必要 |
| audit preset / test を追加するか | 保留 | コード実装扱いになるためユーザー確認が必要 |
| Requirement Definition Gate ロジックを実装するか | 保留 | 判定責務を RanD / manual-bb / code-to-gate のどこに置くか確認が必要 |

## 5. 文書だけで進めてよい作業

- `requirements_audit_packet.json` sample の説明追加
- discovery / audit の契約差分の明文化
- Task Seed の粒度整理
- Acceptance Record の draft 方針整理
- gate verdict の手動判定手順の文章化

## 6. ユーザー確認が必要な作業

- `research-runtime/src/**` の修正
- audit preset の追加
- audit fixture の追加
- audit test の追加
- sample JSON の fixture 昇格
- `uv.lock` の採用
- 先行コード差分の revert

## 7. 次の推奨順

1. discovery mode 先行コード差分のレビュー観点を使い、正式採用可否を判断する。
2. audit sample を fixture に昇格するか判断する。
3. audit preset / test を追加するか判断する。
4. Requirement Definition Gate の実装責務を RanD / manual-bb / code-to-gate のどこに置くか決める。
5. 実装へ進む場合は、Task Seed を実装 PR 単位に切る。
