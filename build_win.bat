@echo off
setlocal EnableDelayedExpansion

echo ========================================
echo   IELTSVocab Windows Build
echo ========================================
echo.

cd /d "%~dp0"

REM 0. check python
where python >nul 2>nul
if errorlevel 1 (
    echo [X] Python not found.
    echo     Please install Python 3.10+ from https://www.python.org/downloads/
    echo     IMPORTANT: check "Add python.exe to PATH" during installation.
    pause
    exit /b 1
)

REM 1. install dependencies
echo [1/4] Installing dependencies...
python -m pip install --quiet -r requirements.txt
if errorlevel 1 (
    echo [X] Failed to install requirements.
    pause
    exit /b 1
)
python -m pip install --quiet pyinstaller pillow
if errorlevel 1 (
    echo [X] Failed to install pyinstaller/pillow.
    pause
    exit /b 1
)

REM 2. clean previous build
echo [2/4] Cleaning previous build...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM 3. run PyInstaller
echo [3/4] Running PyInstaller (1-2 minutes)...
python -m PyInstaller --noconfirm --clean IELTSVocab_win.spec
if not exist "dist\IELTSVocab\IELTSVocab.exe" (
    echo [X] Build failed: dist\IELTSVocab\IELTSVocab.exe not found.
    pause
    exit /b 1
)

REM 4. zip the output folder
echo [4/4] Creating zip archive...
cd dist
powershell -NoProfile -Command "Compress-Archive -Path IELTSVocab -DestinationPath IELTSVocab-win.zip -Force"
cd ..

echo.
echo ========================================
echo   BUILD COMPLETE
echo ========================================
echo.
echo Output:
echo   Folder:  dist\IELTSVocab\
echo   Exe:     dist\IELTSVocab\IELTSVocab.exe
echo   Zip:     dist\IELTSVocab-win.zip
echo.
echo Test:    double-click dist\IELTSVocab\IELTSVocab.exe
echo Share:   send IELTSVocab-win.zip to friends
echo.
pause
