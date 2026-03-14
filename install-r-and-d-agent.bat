@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "INSTALLER_DIR=%SCRIPT_DIR%r-and-d-agent-installer"
set "ARGS=-Mode auto"

if not exist "%INSTALLER_DIR%\scripts\install.ps1" (
  echo installer script not found: "%INSTALLER_DIR%\scripts\install.ps1"
  exit /b 1
)

for %%A in (%*) do (
  if /I "%%~A"=="--force" set "ARGS=%ARGS% -Force"
  if /I "%%~A"=="--skip-optional" set "ARGS=%ARGS% -SkipOptional"
  if /I "%%~A"=="--local" set "ARGS=-Mode local"
  if /I "%%~A"=="--remote" set "ARGS=-Mode remote"
)

powershell -ExecutionPolicy Bypass -NoProfile -File "%INSTALLER_DIR%\scripts\install.ps1" %ARGS%
if errorlevel 1 exit /b %errorlevel%

echo.
echo status:
powershell -ExecutionPolicy Bypass -NoProfile -File "%INSTALLER_DIR%\scripts\status.ps1"

endlocal
