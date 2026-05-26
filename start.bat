@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ════════════════════════════════════════
echo   IELTS Vocab — 启动中
echo ════════════════════════════════════════
echo.

REM 检查 Python
where python >nul 2>nul
if errorlevel 1 (
    echo [X] 未检测到 Python
    echo.
    echo 请先安装 Python 3.10+:
    echo   1. 访问 https://www.python.org/downloads/
    echo   2. 下载并安装最新版本
    echo   3. 安装时务必勾选 "Add python.exe to PATH"
    echo   4. 装完后重新双击本 start.bat
    echo.
    echo 或者：使用打包好的 IELTSVocab.exe（无需装 Python）
    echo.
    pause
    exit /b 1
)

REM 创建虚拟环境（如不存在）
if not exist "venv" (
    echo [1/3] 首次启动，创建虚拟环境...
    python -m venv venv
    if errorlevel 1 (
        echo [X] 虚拟环境创建失败
        pause
        exit /b 1
    )
)

REM 激活虚拟环境
call venv\Scripts\activate.bat

REM 安装依赖
echo [2/3] 安装/校验依赖...
pip install -q -r requirements.txt
if errorlevel 1 (
    echo [X] 依赖安装失败，请检查网络
    pause
    exit /b 1
)

echo [3/3] 启动 Flask 服务...
echo.

REM 后台启动 Flask
start /B python app.py

REM 等待服务就绪
timeout /t 2 /nobreak >nul

REM 打开浏览器
start http://127.0.0.1:5000

echo ════════════════════════════════════════
echo   应用已启动 → 浏览器自动打开
echo   关闭此窗口将停止服务
echo ════════════════════════════════════════
pause
