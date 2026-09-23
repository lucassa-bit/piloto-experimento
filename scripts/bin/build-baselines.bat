@echo off
setlocal

set "BIN=%~dp0"
set "BIN=%BIN:~0,-1%"
for %%I in ("%BIN%\..") do set "SCRIPTS=%%~fI"
for %%I in ("%SCRIPTS%\..") do set "ROOT=%%~fI"

set "CLARIFY_ROOT=%ROOT%"
set "PYTHONPATH=%SCRIPTS%"

echo Generating baselines with $speckit-specify...
echo Root: %ROOT%
echo.

call python "%SCRIPTS%\baseline-gen\runner.py" %*
set "EXITCODE=%ERRORLEVEL%"

echo.
if %EXITCODE% equ 0 (
    echo Finished.
    echo Check baselines\<US>\spec.md and collected-data\baseline-generation.csv
) else (
    echo Command failed with exit code %EXITCODE%.
)
echo.
pause
endlocal
exit /b %EXITCODE%
