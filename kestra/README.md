# RanD Kestra Flows

このディレクトリには、`research-runtime` を Kestra から起動するための flow 定義を置いています。

## 含まれる flow

- `research-manual-run.yaml`
  - webhook で任意 preset を実行する汎用 flow
- `research-ai-watch-daily.yaml`
  - `ai_watch_daily` を朝に起動する schedule flow
- `research-arxiv-nightly.yaml`
  - `paper_arxiv_ai_recent` を夜に起動する schedule flow

## 役割

- `pulse-kestra` や外部 webhook から `research-runtime` を呼べるようにする
- run ごとの `report.json` と `state_context.json` を Kestra の outputFiles に残す
- `research-runtime` 側で実施している taskstate / memx / tracker 連携を Kestra 実行でも利用する

## 前提

- Kestra secrets:
  - `RAND_RESEARCH_WEBHOOK_KEY`
- Kestra globals:
  - `rand_runtime_root`
  - `kestra_base_url`

## 補足

本 flow は `pulse-kestra` の mention 系 flow を置き換えるものではなく、RanD の調査系パイプラインを Kestra 側へ接続するための追加 flow です。
