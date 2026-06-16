#!/bin/bash
cd "$(dirname "$0")"

echo "======================================"
echo "    🤖 AI 多轮对话系统"
echo "======================================"

# 检查 node
if ! command -v node &> /dev/null; then
  # 尝试 homebrew 路径
  export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
fi

if ! command -v node &> /dev/null; then
  echo "❌ 未找到 Node.js，请先安装："
  echo "   brew install node"
  read -p "按回车键退出..."
  exit 1
fi

echo "✅ Node.js: $(node -v)"

# 安装依赖
if [ ! -d "node_modules" ]; then
  echo ""
  echo "📦 首次运行，正在安装依赖（约需1分钟）..."
  npm install
  if [ $? -ne 0 ]; then
    echo "❌ 安装依赖失败，请检查网络连接"
    read -p "按回车键退出..."
    exit 1
  fi
  echo "✅ 依赖安装完成！"
fi

echo ""
echo "🚀 正在启动服务器..."
echo ""

# 启动服务器
node server.js &
SERVER_PID=$!

# 等待服务器启动
sleep 2

# 打开浏览器
open http://localhost:3456

echo ""
echo "📌 服务已在后台运行，浏览器已打开"
echo "   地址: http://localhost:3456"
echo ""
echo "关闭此窗口或按 Ctrl+C 停止服务"
echo ""

# 等待服务器
wait $SERVER_PID