# RanD

`RanD` は、R&D Agent アーキテクチャを「導入する場所」と「実際に回す場所」をまとめたルートリポジトリです。

このディレクトリでやっていることは大きく 2 つです。

1. 必要な OSS 群を固定コミットで導入する
2. 論文・AI ニュースの調査パイプラインをすぐ回せるようにする

## 入口

- アーキテクチャ文書: [docs/architecture.md](/Users/ryo-n/Codex_dev/RanD/docs/architecture.md)
- 導入用リポジトリ: [r-and-d-agent-installer](/Users/ryo-n/Codex_dev/RanD/r-and-d-agent-installer)
- 調査ランタイム: [research-runtime](/Users/ryo-n/Codex_dev/RanD/research-runtime)
- ルート入口バッチ:
  - [install-r-and-d-agent.bat](/Users/ryo-n/Codex_dev/RanD/install-r-and-d-agent.bat)
  - [run-research-once.bat](/Users/ryo-n/Codex_dev/RanD/run-research-once.bat)
  - [run-research-schedule.bat](/Users/ryo-n/Codex_dev/RanD/run-research-schedule.bat)

## これは何をするリポジトリか

`RanD` 自体は単独の巨大アプリではありません。実際には次の 2 層を束ねる親リポジトリです。

- 導入層:
  - `r-and-d-agent-installer` が必要な OSS 群を固定コミットで取得します。
  - 導入先の実体は `r-and-d-agent-installer/.installed/` に置かれ、Git では無視されます。
- 実行層:
  - `research-runtime` が source preset に従って調査を走らせ、収集・正規化・評価・state 保存までを担当します。
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

## どういう風に動くか

実行の流れは次のとおりです。

1. `install-r-and-d-agent.bat` で必要リポジトリを導入する
2. `run-research-once.bat <preset>` か `run-research-schedule.bat` を起動する
3. `research-runtime` が preset を読み、対象サイトを巡回する
4. 収集結果を `NormalizedItem` 形式にそろえ、URL または title ベースで重複除去する
5. `insight-agent` に渡して洞察候補を作る
6. `high_priority=true` の候補だけ `experiment-gate` に渡して Go / Hold / No-Go を付ける
7. `agent-taskstate` 形式の state を更新する
8. `memx-resolver` 用 journal と `tracker-bridge-materials` 用 sync payload を保存する
9. `report.md` と `report.json` を `runs/<run_id>/` に残す

要するに、「集める」だけではなく、「読む価値」「次に何を試すか」「どこへ連携するか」までまとめて 1 run に閉じ込める構成です。

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

現状の `research-runtime` は、この E2E のうち「調査から state 保存まで」をローカルで先に回せるようにした実装です。つまり今は、

- ローカル即実行の入口:
  - `run-research-once.bat`
  - `run-research-schedule.bat`
- 将来の本来運用の入口:
  - `pulse-kestra`
  - `Kestra`

という二段構えになっています。

まだこのリポジトリ内には Kestra flow 定義そのものは置いていません。README 上では「本来のアーキテクチャは Kestra 中心」「現状実装済みなのはローカル実行ランタイム」と読み分けるのが正しいです。

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
  - run 状態を `queued / running / done / needs_review` で保持する
- `memx-resolver`
  - 読んだものの要点と artifact 参照を journal として残す
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

## バージョン固定

導入対象の各リポジトリは [components.json](/Users/ryo-n/Codex_dev/RanD/r-and-d-agent-installer/manifests/components.json) の `pinnedCommit` に固定されます。

つまり、GitHub 側や `Codex_dev` 側のリポジトリが更新されても、`install-r-and-d-agent.bat` が導入する版は変わりません。再現したい構成を壊さずに更新判断できます。
