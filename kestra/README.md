# RanD Kestra Flows

このディレクトリには、`research-runtime` を Kestra から起動するための公開向けサンプル flow を置いています。作者ローカル専用の固定パスは持たず、Kestra globals と secrets で環境差を吸収する前提です。

## 含まれる flow

- `research-manual-run.yaml`
  - webhook で任意 preset を実行する汎用 flow
- `research-ai-watch-daily.yaml`
  - JST 08:00 に `ai_watch_daily` を起動する schedule flow
- `research-arxiv-nightly.yaml`
  - JST 23:00 に `paper_arxiv_ai_recent` を起動する schedule flow
- `research-heartbeat.yaml`
  - event/manual 起点で preset を補完し、runtime 実行と stuck task 監視を行う flow

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

`research-heartbeat.yaml` を UI から手動実行する場合は、inputs に次を渡せます。

```yaml
preset: ai_watch_daily
max_items: 12
```

## 役割の分離

- preset 選択規則の正本
  - `research-runtime/configs/heartbeat.json`
- 定時実行時刻の正本
  - `research-ai-watch-daily.yaml`
  - `research-arxiv-nightly.yaml`
- manual / event 起点の preset 補完
  - `research-heartbeat.yaml`

## 役割

- `pulse-kestra` や外部 webhook から `research-runtime` を呼べるようにする
- `report.json` と `state_context.json` を Kestra 側の outputFiles に残す
- `research-runtime` 側の taskstate / memx / tracker 連携を Kestra 実行でも利用する

## 読み方のポイント

- `research-manual-run.yaml`
  - 最小の実行 contract を表す入口 flow
- `research-ai-watch-daily.yaml`, `research-arxiv-nightly.yaml`
  - `timezone: Asia/Tokyo` を持つ定時実行 wrapper
- `research-heartbeat.yaml`
  - schedule を持たない event/manual 補完 flow
