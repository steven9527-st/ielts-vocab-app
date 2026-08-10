@echo off
chcp 65001 >nul
echo ========================================
echo   雅思词汇记忆 App - Windows 打包脚本
echo ========================================
echo.
echo [提示] 请确保已安装 Python 并勾选"Add to PATH"
echo.
echo [1/3] 安装依赖...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [错误] 依赖安装失败
    pause
    exit /b 1
)
echo [2/3] 打包中（可能需要几分钟）...
python -m PyInstaller IELTSVocab-dictation-win.spec --noconfirm --clean
if %errorlevel% neq 0 (
    echo [错误] 打包失败
    pause
    exit /b 1
)
echo [3/3] 打包完成！
echo.
echo 输出文件：dist\IELTSVocab-dictation\IELTSVocab-dictation.exe
echo 将整个 dist\IELTSVocab-dictation 文件夹发给其他人即可运行。
pause
