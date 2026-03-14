# Verification

```powershell
.\scripts\env-check.ps1
.\scripts\run-once.ps1 -Preset paper_arxiv_ai_recent
.\scripts\run-once.ps1 -Preset ai_news_official
$env:PYTHONPATH=(Join-Path (Get-Location) 'src')
python -m unittest discover tests
```

## 合格条件

- `runs/` 配下に run ディレクトリが作られる
- `report.md`, `report.json`, `meta.json` が生成される
- `paper_arxiv_ai_recent` で `arxiv.org` の item が最低 1 件出る
- `ai_news_official` で公式ニュース系の item が最低 1 件出る
- `state/taskstate.json`, `state/memx-journal.json`, `state/tracker-sync.json` が更新される

## Provider Default

- 既定は openrouter -> libaba の順で使う
- .env に両方あれば LLM_PROVIDER=openrouter と LLM_PROVIDER_SEQUENCE=openrouter,alibaba を自動設定する

