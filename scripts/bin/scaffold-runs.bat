@echo off
setlocal

set "BIN=%~dp0"
set "BIN=%BIN:~0,-1%"
for %%I in ("%BIN%\..") do set "SCRIPTS=%%~fI"
for %%I in ("%SCRIPTS%\..") do set "ROOT=%%~fI"

set "CLARIFY_ROOT=%ROOT%"
set "PYTHONPATH=%SCRIPTS%"

echo Scaffolding clarification run folders...
echo Root: %ROOT%
echo.

call python "%SCRIPTS%\clarification-gen\scaffold_runs.py" %*
set "EXITCODE=%ERRORLEVEL%"

echo.
if %EXITCODE% equ 0 (
    echo Finished.
) else (
    echo Command failed with exit code %EXITCODE%.
)
echo.
endlocal
exit /b %EXITCODE%
