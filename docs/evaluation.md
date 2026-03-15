# RanD Evaluation

## 1. 目的

本書は [requirements.md](/Users/ryo-n/Codex_dev/RanD/docs/requirements.md) と [specification.md](/Users/ryo-n/Codex_dev/RanD/docs/specification.md) に対する受け入れ基準を定義する。

## 2. Acceptance Criteria

| ID | 観点 | 判定方法 |
| --- | --- | --- |
| AC-01 | Kestra flow 存在 | `kestra/flows/` に 3 flow が存在する |
| AC-02 | state-aware 実行 | `report.json` に `state_context.before/after` が含まれる |
| AC-03 | 既読判定 | 既知 URL を含む入力で `seen_before=true` と `high_priority=false` が確認できる |
| AC-04 | artifact 完備 | 8 種の artifact が run directory に保存される |
| AC-05 | env loading | `env-check` で依存 repo と provider 順が確認できる |
| AC-06 | tracker optionality | tracker 不達でも run 自体は保存される |
| AC-07 | 文書整合 | `requirements`, `specification`, `architecture` が矛盾しない |

## 3. 検証コマンド

```powershell
cd C:\Users\ryo-n\Codex_dev\RanD\research-runtime
$env:PYTHONPATH = 'C:\Users\ryo-n\Codex_dev\RanD\research-runtime\src'
python -m unittest discover tests
python -m rand_research.cli env-check
```

## 4. 手動確認項目

- [ ] `README.md` から docs への導線が分かる
- [ ] `requirements.md` に測定可能な要求がある
- [ ] `specification.md` に payload / state / flow の仕様がある
- [ ] `tracker` が state 正本でないことが明記されている
- [ ] `agent-taskstate` と `memx-resolver` の読み書き境界が明記されている
