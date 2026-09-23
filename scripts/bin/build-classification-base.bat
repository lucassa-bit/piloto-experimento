@echo off
setlocal

set "BIN=%~dp0"
set "BIN=%BIN:~0,-1%"
for %%I in ("%BIN%\..") do set "SCRIPTS=%%~fI"
for %%I in ("%SCRIPTS%\..") do set "ROOT=%%~fI"

set "CLARIFY_ROOT=%ROOT%"
set "PYTHONPATH=%SCRIPTS%"

echo Building classification base...
echo Root: %ROOT%
echo.

call python "%SCRIPTS%\clarification-processing\build_classification_base.py"
set "EXITCODE=%ERRORLEVEL%"

echo.
if %EXITCODE% equ 0 (
    echo Finished.
    echo Check collected-data\classification_base.csv
) else (
    echo Command failed with exit code %EXITCODE%.
)
echo.
pause
endlocal
exit /b %EXITCODE%
