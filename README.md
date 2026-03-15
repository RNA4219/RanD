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
  - `r-and-d-agent-installer` が `open_deep_research`、`insight-agent`、`experiment-gate`、`agent-taskstate`、`memx-resolver`、`tracker-bridge-materials` などを固定コミットで取得します。
  - 導入先の実体は `r-and-d-agent-installer/.installed/` に置かれ、Git では無視されます。
- 実行層:
  - `research-runtime` が source preset に従って調査を走らせ、収集・正規化・評価・state 保存までを担当します。
  - 実行成果物は `research-runtime/runs/<run_id>/` に保存されます。

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
