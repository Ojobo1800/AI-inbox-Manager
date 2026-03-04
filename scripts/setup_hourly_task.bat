@echo off
REM Batch file to set up email processing task (every 10 minutes)
REM Run this with administrator privileges

echo.
echo ==================================================================
echo Setting up email processing task (every 10 minutes)...
echo ==================================================================
echo.

powershell -ExecutionPolicy Bypass -File "%~dp0setup_hourly_task.ps1"

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ==================================================================
    echo Task setup complete!
    echo ==================================================================
    echo.
) else (
    echo.
    echo ==================================================================
    echo Task setup FAILED
    echo ==================================================================
    echo.
    echo Please run this script as Administrator
    echo.
)

pause
