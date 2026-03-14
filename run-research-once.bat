@echo off
setlocal
set "RUNTIME_DIR=%~dp0research-runtime"
if not exist "%RUNTIME_DIR%\scripts\run-once.ps1" (
  echo runtime script not found: "%RUNTIME_DIR%\scripts\run-once.ps1"
  exit /b 1
)
set "PRESET=%~1"
if "%PRESET%"=="" set "PRESET=paper_arxiv_ai_recent"
powershell -ExecutionPolicy Bypass -NoProfile -File "%RUNTIME_DIR%\scripts\run-once.ps1" -Preset "%PRESET%"
endlocal
