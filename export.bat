@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
python -B pipeline\data_extraction\export.py %*
echo.
if "%~1"=="" set /p "SZD_EXPORT_CLOSE=Press Enter to close..."
exit /b %ERRORLEVEL%
