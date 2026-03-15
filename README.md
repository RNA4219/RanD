# RanD

`RanD` は、R&D Agent アーキテクチャを「導入する場所」と「実際に回す場所」に分けて運用するための親リポジトリです。

このリポジトリで担う主な役割は次の 2 つです。

1. 必要な OSS 群を固定コミットで導入する
2. 論文・AI ニュースの調査パイプラインをローカル実行と Kestra 実行の両方で回せるようにする

## 入口

- アーキテクチャ文書: [docs/architecture.md](/Users/ryo-n/Codex_dev/RanD/docs/architecture.md)
- 要件定義: [docs/requirements.md](/Users/ryo-n/Codex_dev/RanD/docs/requirements.md)
- 仕様書: [docs/specification.md](/Users/ryo-n/Codex_dev/RanD/docs/specification.md)
- 受け入れ基準: [docs/evaluation.md](/Users/ryo-n/Codex_dev/RanD/docs/evaluation.md)
- 導入用リポジトリ: [r-and-d-agent-installer](/Users/ryo-n/Codex_dev/RanD/r-and-d-agent-installer)
- 調査ランタイム: [research-runtime](/Users/ryo-n/Codex_dev/RanD/research-runtime)
- Kestra flow 定義: [kestra/README.md](/Users/ryo-n/Codex_dev/RanD/kestra/README.md)
- ルート入口バッチ:
  - [install-r-and-d-agent.bat](/Users/ryo-n/Codex_dev/RanD/install-r-and-d-agent.bat)
  - [run-research-once.bat](/Users/ryo-n/Codex_dev/RanD/run-research-once.bat)
  - [run-research-schedule.bat](/Users/ryo-n/Codex_dev/RanD/run-research-schedule.bat)

## 文書の読み順

`RanD` の設計と実装の正本は文書ごとに役割を分けています。

- [docs/architecture.md](/Users/ryo-n/Codex_dev/RanD/docs/architecture.md)
  - 全体アーキテクチャ、構成要素、責務分担
- [docs/requirements.md](/Users/ryo-n/Codex_dev/RanD/docs/requirements.md)
  - 何を満たせば運用可能とみなすかの要求と受け入れ条件
- [docs/specification.md](/Users/ryo-n/Codex_dev/RanD/docs/specification.md)
  - データモデル、artifact 契約、Kestra flow、外部 repo 契約
- [docs/evaluation.md](/Users/ryo-n/Codex_dev/RanD/docs/evaluation.md)
  - 検収時の確認観点と検証手順

設計変更や追加実装を行うときは、基本的に `architecture -> requirements -> specification -> evaluation` の順に整合を確認します。

## これは何をするリポジトリか

`RanD` 自体は単独の巨大アプリではありません。実際には次の 2 層を束ねる親リポジトリです。

- 導入層:
  - `r-and-d-agent-installer` が必要な OSS 群を固定コミットで取得します。
  - 導入先の実体は `r-and-d-agent-installer/.installed/` に置かれ、Git では無視されます。
- 実行層:
  - `research-runtime` が source preset に従って調査を走らせ、収集・正規化・評価・state 保存までを担当します。
  - `kestra/flows/` は `research-runtime` を Kestra から起動するための flow 定義です。
  - 実行成果物は `research-runtime/runs/<run_id>/` に保存されます。

## 導入層に含まれるアプリケーション

`r-and-d-agent-installer` が導入対象として扱う OSS は次のとおりです。

- `open_deep_research`
  - 調査と探索の中核
- `llm-guard`
  - 外部入力や出力候補に対するガード層
- `kestra`
  - ワークフロー制御の本体
- `pulse-kestra`
  - 外部イベントや heartbeat を Kestra に橋渡しする入口
- `agent-taskstate`
  - 実行状態と再開ポイントの保持
- `experiment-gate`
  - Go / Hold / No-Go 判定
- `ai-product-requirement-document`
  - 実装ハンドオフ用の PRD 出口
- `Roadmap-Design-Skill`
  - 採択済みテーマを計画へ落とす層
- `strategy-guided-policy-prompt`
  - 調査方針と判断方針のガイド
- `insight-agent`
  - 文書やソースから insight を抽出する層
- `memx-resolver`
  - 参照知識、読了記録、補助コンテキストの層
- `tracker-bridge-materials`
  - GitHub Issues / Jira / Linear / Backlog などへの外部同期層
- `workflow-cookbook`
  - 実行レシピや handoff の補助

## 実行の全体像

ローカル実行の基本フローは次のとおりです。

1. `install-r-and-d-agent.bat` で必要リポジトリを導入する
2. `run-research-once.bat <preset>`、`run-research-schedule.bat`、または CLI の `heartbeat` を起動する
3. `research-runtime` が preset を読み、対象サイトを巡回する
4. 実行前に `agent-taskstate` 相当の task state と `memx-resolver` 相当の journal state を読み、同じ preset の過去 run を把握する
5. 収集結果を `NormalizedItem` 形式に正規化し、URL または title ベースで重複除去する
6. 過去に読んだ URL は `seen_before=true` として印付けし、priority と gate 対象を自動で落とす
7. `insight-agent` に渡して洞察候補を作る
8. `high_priority=true` の候補だけ `experiment-gate` に渡して Go / Hold / No-Go を付ける
9. `agent-taskstate` 形式の state を更新する
10. `memx-resolver` 用 journal と `tracker-bridge-materials` 用 sync payload を保存する
11. `report.md`, `report.json`, `insight.json`, `gate.json`, `meta.json`, `memx_journal.json`, `tracker_sync.json`, `state_context.json` を `runs/<run_id>/` に保存する

要するに、「集める」だけではなく、「過去に何を読んでどう処理したか」を踏まえて次の run を調整する構成です。

## state をどう使っているか

`research-runtime` は run の前後で state を扱います。

- 実行前:
  - `research-runtime/state/taskstate.json` を読み、同じ preset の過去 task と未完了 task を把握します
  - `research-runtime/state/memx-journal.json` を読み、過去 run で読んだ URL を把握します
- 実行中:
  - `queued -> running -> done / needs_review / failed` で task state を更新します
  - 過去に読んだ item には `previously_seen` タグを付け、gate の優先対象から外しやすくします
- 実行後:
  - `taskstate.json`, `memx-journal.json`, `tracker-sync.json` を更新します
  - `report.json` に `state_context` と `artifacts` を埋め込みます
  - `runs/<run_id>/state_context.json` に before / after の snapshot を残します

## Kestra を使う場合の流れ

アーキテクチャ上の正規ルートは、ローカル bat 実行よりも `pulse-kestra` と `Kestra` を中核にした流れです。

1. `pulse-kestra` が mention / webhook / cron / heartbeat を受ける
2. `Kestra` が flow を起動する
3. 必要なら `llm-guard` で入力をガードする
4. `open_deep_research` で調査を開始する
5. `insight-agent` で洞察候補を構造化する
6. `experiment-gate` で Go / Hold / No-Go を付ける
7. `Roadmap-Design-Skill` で next actions に落とす
8. `agent-taskstate` に実行状態を保存する
9. `tracker-bridge-materials` で外部トラッカーへ同期する

現状の `research-runtime` は、この E2E のうち「調査から state 保存まで」をローカルでも先に回せるようにした実装です。

## Kestra flow 一覧

現在 `RanD` が持つ flow は次の 4 つです。

- [research-manual-run.yaml](/Users/ryo-n/Codex_dev/RanD/kestra/flows/research-manual-run.yaml)
  - webhook で任意 preset を実行する汎用 flow
- [research-ai-watch-daily.yaml](/Users/ryo-n/Codex_dev/RanD/kestra/flows/research-ai-watch-daily.yaml)
  - `ai_watch_daily` を定期起動する schedule flow
- [research-arxiv-nightly.yaml](/Users/ryo-n/Codex_dev/RanD/kestra/flows/research-arxiv-nightly.yaml)
  - `paper_arxiv_ai_recent` を夜間巡回する schedule flow
- [research-heartbeat.yaml](/Users/ryo-n/Codex_dev/RanD/kestra/flows/research-heartbeat.yaml)
  - heartbeat 起点で定期巡回や回復監視へつなぐ flow

## source と preset

いまの調査対象は preset で固定しています。

- `paper_arxiv_ai_recent`
  - 主入口は [arXiv cs.AI recent](https://arxiv.org/list/cs.AI/recent)
  - 補助的に Hugging Face Papers と Papers with Code も見る
- `ai_news_official`
  - OpenAI News
  - Anthropic News
  - Google DeepMind Blog
  - Google AI Blog
- `ai_watch_daily`
  - 上の 2 つをまとめて流す合成 preset

## 実行時に使う主なリポジトリ

- `open_deep_research`
  - 調査の入口となる source preset / prompt 管理の前提
- `insight-agent`
  - 収集した item を構造化して insight を作る
- `experiment-gate`
  - PoC を試す価値があるかを `go / hold / no_go` で判定する
- `agent-taskstate`
  - run 状態を `queued / running / done / needs_review / failed` で保持する
- `memx-resolver`
  - 読んだものの要点と artifact 参照を journal として残し、次回 run の既読判定にも使う
- `tracker-bridge-materials`
  - gate の推奨アクションを外部トラッカー同期向け payload として残す

## どこに何が保存されるか

1 回の run ごとに `research-runtime/runs/<run_id>/` へ次を保存します。

- `report.md`
- `report.json`
- `insight.json`
- `gate.json`
- `meta.json`
- `memx_journal.json`
- `tracker_sync.json`
- `state_context.json`

`report.json` には次も含まれます。

- `state_context.before`
- `state_context.after`
- `artifacts`
- `taskstate_refs`
- `memx_refs`
- `tracker_sync_refs`

横断 state は次に保存されます。

- task state: [research-runtime/state/taskstate.json](/Users/ryo-n/Codex_dev/RanD/research-runtime/state/taskstate.json)
- memx journal: [research-runtime/state/memx-journal.json](/Users/ryo-n/Codex_dev/RanD/research-runtime/state/memx-journal.json)
- tracker sync log: [research-runtime/state/tracker-sync.json](/Users/ryo-n/Codex_dev/RanD/research-runtime/state/tracker-sync.json)

## セットアップ

通常インストール:

```bat
install-r-and-d-agent.bat
```

必須コンポーネントだけ入れる:

```bat
install-r-and-d-agent.bat --skip-optional
```

既存導入を作り直す:

```bat
install-r-and-d-agent.bat --force
```

## 実行例

`arXiv cs.AI recent` を 1 回回す:

```bat
run-research-once.bat paper_arxiv_ai_recent
```

公式 AI ニュースを 1 回回す:

```bat
run-research-once.bat ai_news_official
```

定期実行設定をまとめて回す:

```bat
run-research-schedule.bat
```

CLI の heartbeat を summary-only で確認する:

```powershell
cd C:\Users\ryo-n\Codex_dev\RanD\research-runtime
$env:PYTHONPATH = 'C:\Users\ryo-n\Codex_dev\RanD\research-runtime\src'
python -m rand_research.cli heartbeat --summary-only --max-items 5
```

依存関係と API 設定を確認する:

```powershell
cd C:\Users\ryo-n\Codex_dev\RanD\research-runtime
.\scripts\env-check.ps1
```

## 動作確認時の前提

- 既存 repo の `.env` を自動ロードします
  - `experiment-gate/.env`
  - `insight-agent/.env`
  - `Roadmap-Design-Skill/.env`
  - `pulse-kestra/bridge/.env`
- 動作確認の既定プロバイダは `openrouter` を主、`alibaba` を次点にします
- 取得タイムアウトは `180 秒`、LLM タイムアウトは `600 秒`、リトライは `4 回` です

## 検証状況

現時点で確認済みなのは次の内容です。

- `python -m unittest discover tests`
  - `6 tests OK`
- `python -m rand_research.cli env-check`
  - `open_deep_research`, `insight-agent`, `experiment-gate`, `agent-taskstate`, `memx-resolver`, `tracker-bridge-materials` が利用可能
  - provider 順は `openrouter -> alibaba`
- `python -m rand_research.cli run-once --preset paper_arxiv_ai_recent --max-items 2`
  - `report.json` に `state_context` と `artifacts` を含むことを確認済み
  - `runs/<run_id>/` に 8 種 artifact が揃うことを確認済み

## バージョン固定

導入対象の各リポジトリは [components.json](/Users/ryo-n/Codex_dev/RanD/r-and-d-agent-installer/manifests/components.json) の `pinnedCommit` に固定されます。

つまり、GitHub 側や `Codex_dev` 側のリポジトリが更新されても、`install-r-and-d-agent.bat` が導入する版は変わりません。再現したい構成を壊さずに更新判断できます。
