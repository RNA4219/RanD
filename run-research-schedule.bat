@echo off
setlocal
set "RUNTIME_DIR=%~dp0research-runtime"
if not exist "%RUNTIME_DIR%\scripts\run-schedule.ps1" (
  echo runtime script not found: "%RUNTIME_DIR%\scripts\run-schedule.ps1"
  exit /b 1
)
powershell -ExecutionPolicy Bypass -NoProfile -File "%RUNTIME_DIR%\scripts\run-schedule.ps1"
endlocal
