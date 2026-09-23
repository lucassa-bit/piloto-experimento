@echo off
setlocal

set "BIN=%~dp0"
set "BIN=%BIN:~0,-1%"
for %%I in ("%BIN%\..") do set "SCRIPTS=%%~fI"
for %%I in ("%SCRIPTS%\..") do set "ROOT=%%~fI"

set "CLARIFY_ROOT=%ROOT%"
set "PYTHONPATH=%SCRIPTS%"

echo Running full clarification pipeline...
echo Root: %ROOT%
echo.
echo Extra args (scaffold): %*
echo.

echo ========== 1/5 scaffold-runs ==========
call python "%SCRIPTS%\clarification-gen\scaffold_runs.py" %*
set "EXITCODE=%ERRORLEVEL%"
if %EXITCODE% neq 0 goto :finish

echo.
echo ========== 2/5 run clarifications ==========
call python "%SCRIPTS%\clarification-gen\runner.py"
set "EXITCODE=%ERRORLEVEL%"
if %EXITCODE% neq 0 goto :finish

echo.
echo ========== 3/5 check-outputs ==========
call python "%SCRIPTS%\check-outputs\check_outputs.py"
set "EXITCODE=%ERRORLEVEL%"
if %EXITCODE% neq 0 goto :finish

echo.
echo ========== 4/5 extract-questions ==========
call python "%SCRIPTS%\clarification-processing\extract_questions.py"
set "EXITCODE=%ERRORLEVEL%"
if %EXITCODE% neq 0 goto :finish

echo.
echo ========== 5/5 build-classification-base ==========
call python "%SCRIPTS%\clarification-processing\build_classification_base.py"
set "EXITCODE=%ERRORLEVEL%"

:finish
echo.
if %EXITCODE% equ 0 (
    echo Pipeline finished.
    echo Check collected-data\ for execution-table.csv, outputs-check.csv,
    echo questions_raw.csv and classification_base.csv
) else (
    echo Pipeline failed with exit code %EXITCODE%.
)
echo.
pause
endlocal
exit /b %EXITCODE%
