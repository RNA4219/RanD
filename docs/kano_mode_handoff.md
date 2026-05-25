---
intent_id: INT-KANO-001
owner: rand
status: active
last_reviewed_at: 2026-05-26
next_review_due: 2026-06-09
---

# KanoMode 引継ぎ資料

## 1. 背景

ユーザーの意図は「workflow-cookbook に従って、KanoMode の要件定義と進行しやすいドキュメントを整備する」ことだった。

途中で、コード実装まで先行して入れてしまった。ユーザーから「コードの実装は頼んでいない」「戻さないで証跡だけ残して」「RUNBOOK と引継ぎ資料に状態を残してほしい」と指示があったため、この資料を作成する。

## 2. 現在の扱い

現在の working tree にあるコード差分は、未承認の正式実装ではなく、次工程の参考証跡である。

- 戻さない。
- 追加で実装を進めない。
- 次に作業するエージェントは、まず文書と Task Seed を整える。
- コード実装へ進む場合は、ユーザー確認後に正式タスクとして扱う。

## 3. ドキュメント実装として完了済みのもの

- [requirements_kano_mode.md](requirements_kano_mode.md)
  - KanoMode の目的、Scope、I/O Contract、FR/NFR、KPI、AC、リスク、検証コマンドを定義した。
- [tasks/TASK-20260526-01-kano-mode-p0.md](tasks/TASK-20260526-01-kano-mode-p0.md)
  - workflow-cookbook の Task Seed 形式に沿って P0 実装タスクを切った。
- [requirements.md](requirements.md)
  - 拡張要件として KanoMode 要件定義と Task Seed への導線を追加した。
- [specification_kano_mode.md](specification_kano_mode.md)
  - workflow-cookbook の仕様書様式に沿って、KanoMode のふるまい、I/O、artifact、互換性、検証観点を定義した。
- [evaluation.md](evaluation.md)
  - AC-K 系の KanoMode Acceptance Criteria を追加した。
- [specification.md](specification.md)
  - KanoMode preset、追加 artifact、offline eval の契約を追記した。
- [../RUNBOOK.md](../RUNBOOK.md)
  - 再開手順と注意事項を追加した。
- [kano_mode_agent_instruction.md](kano_mode_agent_instruction.md)
  - 次のエージェント向けに、読む順番、触ってよい範囲、ユーザー確認が必要な範囲を明文化した。

## 4. 先行して入っているコード差分

以下は「証跡として残す」対象であり、正式採用は未判断。

- `research-runtime/src/rand_research/kano.py`
  - evidence から `kano.json` / `requirements_packet.json` 相当の payload を作る helper。
- `research-runtime/src/rand_research/fetchers.py`
  - `kano_query_seed`
  - `kano_fixture_json`
- `research-runtime/src/rand_research/pipeline.py`
  - `preset.mode == "kano_requirements"` のとき追加 artifact を生成する分岐。
  - `preset.insight_enabled` で insight 実行を preset 単位で無効化する分岐。
- `research-runtime/src/rand_research/reports.py`
  - `extra_payloads` を artifact と report payload に含める拡張。
- `research-runtime/configs/presets/kano_requirements_hybrid.json`
  - query seed ベースの KanoMode preset。
- `research-runtime/configs/presets/kano_requirements_offline_eval.json`
  - fixture ベースの offline eval preset。
- `research-runtime/prompts/kano_requirements_prompt.md`
  - KanoMode prompt 草案。
- `research-runtime/tests/fixtures/kano_evidence.json`
  - offline eval fixture。
- `research-runtime/tests/test_kano.py`
  - packet 生成 helper のテスト。
- `research-runtime/tests/test_fetchers.py`
  - Kano fetcher 追加分のテスト。
- `research-runtime/tests/test_reports.py`
  - extra artifact 保存のテスト。
- `research-runtime/pyproject.toml`
  - Windows の `zoneinfo` 解決用に `tzdata` を追加。
- `research-runtime/uv.lock`
  - `uv run` により生成された lockfile。

## 5. 検証証跡

先行コード差分を含む状態で、次を確認済み。

```powershell
cd research-runtime
uv run python -m unittest discover tests
```

結果:

```text
Ran 29 tests in 2.622s
OK
```

次の offline eval も実行済み。

```powershell
cd research-runtime
uv run python -m rand_research.cli run-once --preset kano_requirements_offline_eval --max-items 5
```

確認結果:

- `status: ok`
- `kano_json` artifact path が report に含まれる
- `requirements_packet_json` artifact path が report に含まれる
- `requirements_packet.requirements` に `must_be` と `attractive` の候補が出る

## 6. 残課題

文書実装として次を優先する。

1. **[解決済み 2026-05-26]** `docs/evaluation.md` AC-K03/K04 を `docs/specification_kano_mode.md` の完全 artifact fields と整合させた。
2. **[提案済み 2026-05-26]** Task Seed を P0-1 / P0-2 / P0-3 に分割する案を `TASK-20260526-01` に追記した。ユーザー確認後に正式採用。
3. **[決定済み 2026-05-26]** Acceptance Record は pilot段階で workflow-cookbook 参照に留める。正式運用開始後 RanD側に作成。`docs/specification_kano_mode.md` 11節に明記。
4. **[追記済み 2026-05-26]** 先行コード差分のレビュー観点を `TASK-20260526-01` Notes節に追加した。

残る未解決事項:

- Task分割の正式採用判断（ユーザー確認待ち）
- 先行コード差分の正式採用判断（ユーザー確認待ち）
- lockfile (`uv.lock`) の採用判断（ユーザー確認待ち）

## 7. 次に触ってよい範囲

ユーザー確認なしで進めてよい範囲:

- RUNBOOK の整理
- requirements / specification / evaluation の整合
- Task Seed の分割
- 引継ぎ資料の更新

ユーザー確認が必要な範囲:

- `research-runtime/src/**` の追加実装
- preset / prompt / fixture の正式採用
- lockfile の採用判断
- 先行コード差分の revert
