@echo off
setlocal

set "BIN=%~dp0"
set "BIN=%BIN:~0,-1%"
for %%I in ("%BIN%\..") do set "SCRIPTS=%%~fI"
for %%I in ("%SCRIPTS%\..") do set "ROOT=%%~fI"

set "CLARIFY_ROOT=%ROOT%"
set "PYTHONPATH=%SCRIPTS%"

echo Running all SpecKit clarify executions...
echo Root: %ROOT%
echo.

call python "%SCRIPTS%\clarification-gen\runner.py"
set "EXITCODE=%ERRORLEVEL%"
if %EXITCODE% neq 0 goto :finish

call python "%SCRIPTS%\check-outputs\check_outputs.py"
set "EXITCODE=%ERRORLEVEL%"

:finish
echo.
if %EXITCODE% equ 0 (
    echo Finished.
    echo Check collected-data\execution-table.csv
) else (
    echo Command failed with exit code %EXITCODE%.
)
echo.
pause
endlocal
exit /b %EXITCODE%
