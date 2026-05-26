@echo off
cd /d "%~dp0"

echo ========================================
echo   IELTS Vocab - Starting
echo ========================================
echo.

REM check Python
where python >nul 2>nul
if errorlevel 1 (
    echo [X] Python not detected.
    echo.
    echo Please install Python 3.10+:
    echo   1. Visit https://www.python.org/downloads/
    echo   2. Download and install the latest version
    echo   3. During install, CHECK "Add python.exe to PATH"
    echo   4. After install, double-click this start.bat again
    echo.
    echo Alternative: use the packaged IELTSVocab.exe (no Python needed)
    echo.
    pause
    exit /b 1
)

REM create venv if not exists
if not exist "venv" (
    echo [1/3] First run, creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo [X] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

REM activate venv
call venv\Scripts\activate.bat

REM install dependencies
echo [2/3] Installing dependencies...
pip install -q -r requirements.txt
if errorlevel 1 (
    echo [X] Failed to install dependencies. Check network connection.
    pause
    exit /b 1
)

echo [3/3] Starting Flask server...
echo.

REM start Flask in background
start /B python app.py

REM wait for server
timeout /t 2 /nobreak >nul

REM open browser
start http://127.0.0.1:5000

echo ========================================
echo   App started - browser will open
echo   Close this window to stop the server
echo ========================================
pause
