# RanD Research Runtime

`RanD` の実行面を担う軽量ワークスペースです。論文・AI ニュースを収集し、構造化し、必要に応じて評価し、成果物と state を保存します。

## 入口

- CLI: `python -m rand_research.cli run-once --preset paper_arxiv_ai_recent`
- PowerShell: `.\scripts\run-once.ps1 -Preset paper_arxiv_ai_recent`
- 定期実行: `.\scripts\run-schedule.ps1`
- 環境確認: `.\scripts\env-check.ps1`

## 役割

- `open_deep_research` を前提にした調査 prompt と source preset を管理
- `insight-agent` / `experiment-gate` / `agent-taskstate` を繋ぐ
- 今回の主成功条件として `memx-resolver` と `tracker-bridge-materials` も接続する
- `runs/` に成果物を保存し、`state/` に軽量 state を残す

- 動作確認の既定プロバイダは openrouter を主、libaba を次点にする


- ランタイムは取得タイムアウト 180 秒、LLM タイムアウト 600 秒、リトライ 4 回に底上げしている

