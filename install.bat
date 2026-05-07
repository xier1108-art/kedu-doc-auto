@echo off
REM ASCII-only launcher. Korean messages are in install.py (UTF-8 safe).
REM This avoids cmd.exe interpreting UTF-8 bytes as cp949 commands.

setlocal

REM Find Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Python is not installed or not in PATH.
    echo Download from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

REM Hand off to Python script (handles all Korean messages safely)
python "%~dp0install.py"
set RC=%errorlevel%

pause
endlocal
exit /b %RC%
