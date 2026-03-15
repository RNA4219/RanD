# RanD Specification

## 1. 本書の位置づけ

本書は [requirements.md](/Users/ryo-n/Codex_dev/RanD/docs/requirements.md) を満たすための、RanD の実装・構成・データ連携仕様を定義する。

- 全体像: [architecture.md](/Users/ryo-n/Codex_dev/RanD/docs/architecture.md)
- 実装優先順位: [next-implementation-priorities.md](/Users/ryo-n/Codex_dev/RanD/docs/next-implementation-priorities.md)
- 要件: [requirements.md](/Users/ryo-n/Codex_dev/RanD/docs/requirements.md)

## 2. システム境界

### 2.1 RanD が持つ責務

- 固定コミットでの依存 repo 導入
- 調査ランタイムの実行
- state-aware な run の保存
- Kestra flow 定義の保持
- 外部コンポーネントをつなぐ親ハブとしての README / docs 整備

### 2.2 外部 repo が持つ責務

- `pulse-kestra`: 外部イベント受信、Webhook bridge
- `kestra`: flow 実行制御
- `agent-taskstate`: task / run / state / decision の正本
- `memx-resolver`: journal / knowledge / docs resolve / ack の正本
- `insight-agent`: insight 抽出
- `experiment-gate`: hypothesis 評価
- `tracker-bridge-materials`: tracker 同期

## 3. ディレクトリ仕様

```text
RanD/
├─ docs/
│  ├─ architecture.md
│  ├─ next-implementation-priorities.md
│  ├─ requirements.md
│  └─ specification.md
├─ r-and-d-agent-installer/
│  ├─ manifests/components.json
│  └─ scripts/
├─ research-runtime/
│  ├─ configs/
│  ├─ prompts/
│  ├─ scripts/
│  ├─ src/rand_research/
│  ├─ state/
│  └─ runs/
├─ kestra/
│  ├─ README.md
│  └─ flows/
└─ *.bat
```

## 4. 実行コンポーネント仕様

### 4.1 Installer

- 実装位置: [r-and-d-agent-installer](/Users/ryo-n/Codex_dev/RanD/r-and-d-agent-installer)
- 設定正本: [components.json](/Users/ryo-n/Codex_dev/RanD/r-and-d-agent-installer/manifests/components.json)
- 役割:
  - 導入対象 repo 一覧を保持する
  - `pinnedCommit` に基づき固定版を導入する
  - `.installed/` を Git 管理外で保持する

### 4.2 Research Runtime

- 実装位置: [research-runtime](/Users/ryo-n/Codex_dev/RanD/research-runtime)
- CLI 入口:
  - `python -m rand_research.cli run-once --preset <name>`
  - `python -m rand_research.cli run-schedule`
  - `python -m rand_research.cli env-check`
- Windows 入口:
  - [run-research-once.bat](/Users/ryo-n/Codex_dev/RanD/run-research-once.bat)
  - [run-research-schedule.bat](/Users/ryo-n/Codex_dev/RanD/run-research-schedule.bat)

### 4.3 Kestra Flows

- 実装位置: [kestra/flows](/Users/ryo-n/Codex_dev/RanD/kestra/flows)
- flow 一覧:
  - [research-manual-run.yaml](/Users/ryo-n/Codex_dev/RanD/kestra/flows/research-manual-run.yaml)
  - [research-ai-watch-daily.yaml](/Users/ryo-n/Codex_dev/RanD/kestra/flows/research-ai-watch-daily.yaml)
  - [research-arxiv-nightly.yaml](/Users/ryo-n/Codex_dev/RanD/kestra/flows/research-arxiv-nightly.yaml)
- 役割:
  - webhook / schedule から `research-runtime` を起動する
  - `report.json` と `state_context.json` を Kestra outputFiles に残す

## 5. データモデル仕様

### 5.1 Run Request

```json
{
  "preset": "paper_arxiv_ai_recent",
  "max_items": 8,
  "event_type": "manual|schedule|heartbeat",
  "source": "kestra.schedule.paper_arxiv_ai_recent"
}
```

### 5.2 NormalizedItem

`research-runtime` 内部では item を以下の共通形式で扱う。

```json
{
  "id": "arxiv-2603.00001",
  "kind": "paper",
  "source_name": "arXiv cs.AI recent",
  "url": "https://arxiv.org/abs/2603.00001",
  "title": "Example Title",
  "published_at": null,
  "authors": [],
  "summary": "...",
  "claims": [],
  "evidence": [],
  "tags": ["paper", "arxiv"],
  "priority": 8,
  "high_priority": true,
  "metadata": {
    "seen_before": false
  }
}
```

### 5.3 ExecutionContext

実行前後に扱う state snapshot は以下の情報を持つ。

```json
{
  "preset": "paper_arxiv_ai_recent",
  "previous_run_count": 3,
  "known_urls": ["https://arxiv.org/abs/2603.00001"],
  "recent_tasks": [],
  "open_tasks": [],
  "recent_memory_entries": []
}
```

### 5.4 Artifacts

1 run につき次の artifact を保存する。

- `report.md`
- `report.json`
- `insight.json`
- `gate.json`
- `meta.json`
- `memx_journal.json`
- `tracker_sync.json`
- `state_context.json`

## 6. state-aware 実行仕様

### 6.1 実行前

`research-runtime` は開始前に以下を読む。

- [taskstate.json](/Users/ryo-n/Codex_dev/RanD/research-runtime/state/taskstate.json)
- [memx-journal.json](/Users/ryo-n/Codex_dev/RanD/research-runtime/state/memx-journal.json)

読み出し内容:

- 同一 preset の過去 task
- 未完了 task
- 過去 run で処理済みの URL
- 最近の memory entry

### 6.2 実行中

- task state を `queued -> running -> done / needs_review` で更新する
- 既知 URL は `seen_before=true` とする
- `seen_before=true` の item は次を適用する
  - `previously_seen` タグ付け
  - priority を下げる
  - `high_priority` を false にする

### 6.3 実行後

- `memx_journal.json` へ source 群と要約を保存する
- `tracker_sync.json` へ tracker 向け sync event を保存する
- before / after の state snapshot を `state_context.json` に保存する

## 7. worker 連携仕様

### 7.1 Insight

- 実装モジュール: `rand_research.integrations.run_insight`
- 入力: `NormalizedItem[]`
- 出力: `insight.json`
- 優先要件:
  - import 成功時は `insight-agent` を利用する
  - 失敗時は fallback insight を返す

### 7.2 Gate

- 実装モジュール: `rand_research.integrations.run_gate`
- 入力: `high_priority=true` かつ未既読の item
- 出力: `gate.json`
- 優先要件:
  - `go / hold / no_go` 相当の判定または fallback を返す
  - 次アクション推奨を含める

### 7.3 Tracker Sync

- 実装モジュール: `rand_research.integrations.write_tracker_sync`
- 出力: `tracker_sync.json`
- 格納内容:
  - preset
  - items
  - gate_recommendations

## 8. Kestra flow 仕様

### 8.1 research-manual-run

- trigger: webhook
- 入力 payload:
  - `preset`
  - `max_items`
  - `event_type`
  - `source`
- 処理:
  1. リクエストをログ出力
  2. `research-runtime` を subprocess で起動
  3. `report.json` と `state_context.json` を保存

### 8.2 research-ai-watch-daily

- trigger: `0 8 * * *`
- 処理:
  - `research-manual-run` の webhook を叩き、`ai_watch_daily` を起動する

### 8.3 research-arxiv-nightly

- trigger: `0 23 * * *`
- 処理:
  - `research-manual-run` の webhook を叩き、`paper_arxiv_ai_recent` を起動する

## 9. 設定仕様

### 9.1 Runtime Config

[configs/runtime.json](/Users/ryo-n/Codex_dev/RanD/research-runtime/configs/runtime.json) は次を持つ。

- `default_max_items`
- `default_timeout_seconds`
- `llm_timeout_seconds`
- `llm_max_retries`
- `llm_retry_backoff_seconds`
- `default_user_agent`
- `enable_gate`
- `enable_insight`
- `enable_memx`
- `enable_tracker_bridge`
- `save_root`
- `state_path`
- `memory_log_path`
- `tracker_sync_path`

### 9.2 Schedule Config

[configs/schedule.json](/Users/ryo-n/Codex_dev/RanD/research-runtime/configs/schedule.json) はローカル bat / PowerShell 実行時の preset 一覧を持つ。

## 10. 検証仕様

最低限の確認は次で行う。

```powershell
cd C:\Users\ryo-n\Codex_dev\RanD\research-runtime
$env:PYTHONPATH = 'C:\Users\ryo-n\Codex_dev\RanD\research-runtime\src'
python -m unittest discover tests
python -m rand_research.cli env-check
```

検証観点:

- state context の読み込みが壊れていない
- seen_before の優先度調整が効く
- 依存 repo が利用可能である
- Kestra flow ファイルがリポジトリ上に存在する

## 11. 今後の拡張点

- `agent-taskstate` CLI / DB との直接統合強化
- `memx-resolver` journal / knowledge への直接書き込み強化
- `llm-guard` の出口適用実装
- `pulse-kestra` heartbeat / replay / resend との本結線
- `tracker-bridge-materials` の実送信モード
- `Roadmap-Design-Skill` / PRD 層への自動昇格
