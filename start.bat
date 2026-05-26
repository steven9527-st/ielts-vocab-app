@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo === 雅思词汇记忆 App ===
echo 正在准备环境...

REM 创建虚拟环境（如不存在）
if not exist "venv" (
    python -m venv venv
)

REM 激活虚拟环境
call venv\Scripts\activate.bat

REM 安装依赖
pip install -q -r requirements.txt

echo 正在启动服务...

REM 后台启动 Flask
start /B python app.py

REM 等待服务就绪
timeout /t 2 /nobreak >nul

REM 打开浏览器
start http://127.0.0.1:5000

echo 应用已启动，请在浏览器中使用。
echo 关闭此窗口将停止服务。
pause
