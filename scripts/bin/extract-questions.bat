@echo off
setlocal

set "BIN=%~dp0"
set "BIN=%BIN:~0,-1%"
for %%I in ("%BIN%\..") do set "SCRIPTS=%%~fI"
for %%I in ("%SCRIPTS%\..") do set "ROOT=%%~fI"

set "CLARIFY_ROOT=%ROOT%"
set "PYTHONPATH=%SCRIPTS%"

echo Extracting questions...
echo Root: %ROOT%
echo.

call python "%SCRIPTS%\clarification-processing\extract_questions.py"
set "EXITCODE=%ERRORLEVEL%"

echo.
if %EXITCODE% equ 0 (
    echo Finished.
    echo Check collected-data\questions.csv
) else (
    echo Command failed with exit code %EXITCODE%.
)
echo.
pause
endlocal
exit /b %EXITCODE%
