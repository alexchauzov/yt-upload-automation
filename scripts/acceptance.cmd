@echo off
REM Acceptance tests entrypoint with mandatory reset
REM Windows version

echo ============================================================
echo RESET TEST ENVIRONMENT
echo ============================================================
python utils/sheets_reset_verify.py
if errorlevel 1 (
    echo.
    echo ERROR: Reset failed. Aborting acceptance tests.
    exit /b 1
)

echo.
echo ============================================================
echo RUN ACCEPTANCE TESTS
echo ============================================================
pytest -v -m acceptance --tb=short
if errorlevel 1 (
    exit /b 1
)

echo.
echo Acceptance tests completed successfully.
exit /b 0
