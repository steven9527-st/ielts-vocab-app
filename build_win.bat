@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

echo ════════════════════════════════════════
echo   IELTSVocab Windows Build
echo ════════════════════════════════════════
echo.

cd /d "%~dp0"

REM 0. 检查 python
where python >nul 2>nul
if errorlevel 1 (
    echo [X] 未检测到 python。请先安装 Python 3.10+ 并勾选 "Add to PATH"
    echo     下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM 1. 装依赖
echo [1/4] 安装/校验依赖...
python -m pip install --quiet -r requirements.txt
python -m pip install --quiet pyinstaller pillow

REM 2. 清理旧产物
echo [2/4] 清理旧产物...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM 3. 构建
echo [3/4] PyInstaller 构建中（约 1-2 分钟）...
python -m PyInstaller --noconfirm --clean IELTSVocab_win.spec

if not exist "dist\IELTSVocab\IELTSVocab.exe" (
    echo [X] 构建失败：dist\IELTSVocab\IELTSVocab.exe 未生成
    pause
    exit /b 1
)

REM 4. 打 zip 包（方便分发）
echo [4/4] 打包 zip...
cd dist
powershell -NoProfile -Command "Compress-Archive -Path IELTSVocab -DestinationPath IELTSVocab-win.zip -Force"
cd ..

echo.
echo ════════════════════════════════════════
echo   构建完成 ✓
echo ════════════════════════════════════════
echo.
echo 产物位置：
echo   文件夹: dist\IELTSVocab\
echo   可执行: dist\IELTSVocab\IELTSVocab.exe
echo   分发包: dist\IELTSVocab-win.zip
echo.
echo 测试方式：
echo   双击 dist\IELTSVocab\IELTSVocab.exe
echo.
echo 分发方式：
echo   把 IELTSVocab-win.zip 发给朋友
echo   朋友解压后双击 IELTSVocab.exe 即用
echo.
pause
