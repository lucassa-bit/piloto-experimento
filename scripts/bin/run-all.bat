@echo off
setlocal EnableExtensions
set "BIN=%~dp0"
where bash >nul 2>&1 || (echo Prefer Git Bash / WSL & exit /b 2)
bash "%BIN%run-all.sh" %*
exit /b %ERRORLEVEL%
