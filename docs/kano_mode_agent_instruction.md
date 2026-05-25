---
intent_id: INT-KANO-001
owner: rand
status: active
last_reviewed_at: 2026-05-26
next_review_due: 2026-06-09
---

# KanoMode 作業エージェント指示文

## 指示

あなたは RanD リポジトリで KanoMode のドキュメント実装を進めるエージェントである。

まず次の順に読むこと。

1. `RUNBOOK.md`
2. `docs/requirements_kano_mode.md`
3. `docs/specification_kano_mode.md`
4. `docs/tasks/TASK-20260526-01-kano-mode-p0.md`
5. `docs/evaluation.md`
6. `docs/kano_mode_handoff.md`

## 最重要ルール

- コード実装を勝手に進めない。
- `research-runtime/src/**`、preset、prompt、fixture、lockfile の正式採用判断にはユーザー確認を取る。
- 既存の先行コード差分は戻さない。
- 先行コード差分は「未承認の正式実装」ではなく「参考証跡」として扱う。
- 文書整備では、要件、仕様、Task Seed、検収、RUNBOOK、引継ぎ資料の整合を優先する。

## 現在の状態

KanoMode について、次の文書は作成済みである。

- `docs/requirements_kano_mode.md`
- `docs/specification_kano_mode.md`
- `docs/tasks/TASK-20260526-01-kano-mode-p0.md`
- `docs/kano_mode_handoff.md`
- `RUNBOOK.md`

一方で、working tree には KanoMode のコード実装に踏み込んだ先行差分も残っている。これは戻さず、証跡として保持する。

## 進めてよい作業

- `docs/requirements_kano_mode.md` と `docs/specification_kano_mode.md` の整合確認
- Task Seed の分割、優先度整理、依存関係整理
- `docs/evaluation.md` の AC-K 系検収条件の明確化
- `RUNBOOK.md` の再開手順と正本導線の整理
- `docs/kano_mode_handoff.md` の証跡更新
- Acceptance Record を作る場合の雛形案作成

## ユーザー確認が必要な作業

- `research-runtime/src/**` の修正
- `research-runtime/configs/presets/**` の正式採用または変更
- `research-runtime/prompts/**` の正式採用または変更
- `research-runtime/tests/**` の追加実装
- `research-runtime/uv.lock` の採用判断
- 先行コード差分の revert
- 実装 PR として扱う判断

## 作業時の出力方針

作業後は、次を簡潔に報告すること。

- 更新した文書
- 整合させた契約
- 未解決事項
- ユーザー確認が必要な事項

コードを触っていない場合は「コード実装には触れていない」と明記する。

## 期待する次の一手

次に進めるなら、まず文書だけで次を行う。

1. `TASK-20260526-01` を P0 のまま維持するか、P0-1 / P0-2 / P0-3 に分割する。
2. `docs/specification_kano_mode.md` の artifact fields と `docs/evaluation.md` の AC-K を突き合わせる。
3. Acceptance Record を RanD 側に作るか、workflow-cookbook 参照に留めるかを決める。
4. 先行コード差分を正式採用する場合のレビュー観点を Task Seed に追加する。
