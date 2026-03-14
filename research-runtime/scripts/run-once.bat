@echo off
setlocal
set "ROOT=%~dp0.."
set "PYTHONPATH=%ROOT%\src"
set "PRESET=%~1"
if "%PRESET%"=="" set "PRESET=paper_arxiv_ai_recent"
python -m rand_research.cli run-once --preset %PRESET%
endlocal
