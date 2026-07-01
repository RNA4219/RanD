---
acceptance_id: AC-20260702-PILOT-RUNTIME
intent_id: INT-RAND-PILOT-RUNTIME-001
owner: rand
status: passed
reviewed_at: 2026-07-02
reviewed_by: codex
approval_type: technical_pilot
release_approval_id: null
---

# RanD pilot runtime acceptance

## Scope

- 対象変更:
  - pilot readiness gate
  - operations outbox remediation
  - pilot snapshot / review artifact
  - pilot status entrypoint
  - pilot accept workflow
  - CLI 分割と artifact validation
- 非対象:
  - Misskey / tracker への実送信
  - external SaaS の delivery 成功保証
  - fixture 外の live web / LLM 品質保証
  - production SLO / dashboard

## Acceptance Criteria

- [x] `pilot-status --summary-only` が日次運用向けの短い状態を返す。
- [x] `pilot-check` が latest run、artifact schema、operations state、heartbeat config、metrics を集約する。
- [x] `outbox-plan` が pending / failed notification の推奨アクションを返す。
- [x] `pilot-snapshot` が readiness、outbox plan、metrics を artifact 化できる。
- [x] `pilot-review` が snapshot に対する判断と follow-up を artifact 化できる。
- [x] `pilot-accept` が snapshot と review を 1 回で保存できる。
- [x] `validate-artifact` が `pilot_snapshot` / `pilot_review` を検査できる。
- [x] `uv run pytest` が通る。

## Evidence

- 実行日: 2026-07-02 JST
- 実行コマンド:
  - `cd research-runtime && uv run pytest`
  - `uv run python -m rand_research.cli pilot-status --summary-only`
  - `uv run python -m rand_research.cli pilot-accept --reviewer codex --notes accepted-for-pilot-runtime`
  - `uv run python -m rand_research.cli pilot-status`
- テスト結果:
  - `uv run pytest`: `91 passed`
- pilot status summary:
  - `status`: `degraded`
  - `latest_run_id`: `20260701-144159-c86a07eb`
  - `pending_outbox_count`: `2`
  - `latest_review_decision`: `accept_with_review`
  - `review_covers_latest_snapshot`: `true`
  - `next_step`: `continue_pilot_with_review`
- pilot accept result:
  - snapshot: `research-runtime/state/pilot-snapshots/pilot-snapshot-20260701T152539-7322480000.json`
  - review: `research-runtime/state/pilot-snapshots/pilot-snapshot-20260701T152539-7322480000.review.json`
  - `snapshot_status`: `degraded`
  - `decision`: `accept_with_review`
  - `required_followup_count`: `3`

## Verification Result

- 判定: passed for pilot runtime
- コメント:
  - 現在の runtime は production-ready ではなく pilot runtime として受け入れる。
  - pending outbox 2 件が残るため `status=degraded` は妥当。
  - `pilot-accept` により snapshot と review が保存され、latest review が latest snapshot を `accept_with_review` でカバーしている。
  - `pilot-status --summary-only` は `continue_pilot_with_review` を返しており、日次運用ではレビュー付き継続が可能。
  - snapshot / review は local operations evidence であり、`research-runtime/state/pilot-snapshots/` は Git 管理外とする。

## Residual Risk

- pending outbox は外部配送結果が未反映である。
- Misskey / tracker 実送信は pulse-kestra 側の責務であり、本 acceptance では dry-run / local outbox までを対象にする。
- live web / LLM 品質は fixture-based gate とは別に pilot evidence を継続収集する。

## Required Follow-up

- pending notification を外部配送結果に応じて `mark-notification --status sent` または `--status failed` で反映する。
- pulse-kestra 側の notifier 実送信結果と `operations-state.json` の照合を別途確認する。
- pilot snapshot / review を定期的に採取し、`continue_pilot_with_review` から `continue_pilot` へ移行できるか確認する。
