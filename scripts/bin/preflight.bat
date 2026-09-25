@echo off
setlocal EnableExtensions
set "BIN=%~dp0"
where bash >nul 2>&1
if errorlevel 1 (
  echo Prefer Git Bash / WSL to run scripts\bin\*.sh
  exit /b 2
)
bash "%BIN%preflight.sh" %*
exit /b %ERRORLEVEL%
