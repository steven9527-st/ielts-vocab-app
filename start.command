#!/bin/bash
cd "$(dirname "$0")"

echo "=== 雅思词汇记忆 App ==="
echo "正在准备环境..."

# 创建虚拟环境（如不存在）
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
pip install -q -r requirements.txt

echo "正在启动服务..."

# 启动 Flask 后台运行
python3 app.py &
FLASK_PID=$!

# 等待服务就绪
sleep 2

# 打开浏览器
open http://127.0.0.1:5000

echo "应用已启动，请在浏览器中使用。关闭此窗口将停止服务。"

# 保持脚本运行（直到用户关闭终端窗口）
wait $FLASK_PID
