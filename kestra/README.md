# RanD Kestra Flows

このディレクトリには、`research-runtime` を Kestra から起動するための公開向けサンプル flow を置いています。作者ローカル専用の固定パスは持たず、Kestra globals と secrets で環境差を吸収する前提です。

## 含まれる flow

- `research-manual-run.yaml`
  - webhook で任意 preset を実行する汎用 flow
- `research-ai-watch-daily.yaml`
  - `ai_watch_daily` を朝に起動する schedule flow
- `research-arxiv-nightly.yaml`
  - `paper_arxiv_ai_recent` を夜に起動する schedule flow
- `research-heartbeat.yaml`
  - time window に応じて preset を自動選択し、heartbeat と stuck task 監視を行う flow

## 公開設定 / example / local 設定

- 公開デフォルト
  - flow 本体。`runtime_root` は `./research-runtime` の example 値を持つだけです。
- example
  - Kestra globals と secrets の例を README に記載します。
- local override
  - 実環境では Kestra globals、secrets、または workspace ごとの設定で差し替えます。

## 必要な globals と secrets

- Secret
  - `RAND_RESEARCH_WEBHOOK_KEY`
- Globals
  - `rand_runtime_root`
  - `kestra_base_url`

サンプル値:

```yaml
rand_runtime_root: ./research-runtime
kestra_base_url: http://localhost:8080
```

## manual 実行の最低入力例

`research-manual-run.yaml` の webhook body は次の形です。

```json
{
  "event_type": "manual",
  "preset": "paper_arxiv_ai_recent",
  "max_items": 5,
  "source": "kestra.webhook.manual"
}
```

## 役割

- `pulse-kestra` や外部 webhook から `research-runtime` を呼べるようにする
- `report.json` と `state_context.json` を Kestra 側の outputFiles に残す
- `research-runtime` 側の taskstate / memx / tracker 連携を Kestra 実行でも利用する

## 読み方のポイント

- `research-manual-run.yaml`
  - 最小の実行 contract を表す入口 flow
- `research-ai-watch-daily.yaml`, `research-arxiv-nightly.yaml`
  - schedule から manual flow を呼ぶ薄い wrapper
- `research-heartbeat.yaml`
  - 自動選択、summary 生成、stuck task 監視を含む運用寄り sample
