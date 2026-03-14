@echo off
setlocal
set "ROOT=%~dp0.."
set "PYTHONPATH=%ROOT%\src"
python -m rand_research.cli run-schedule
endlocal
