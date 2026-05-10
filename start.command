#!/bin/bash
# Verbatim 一键启动脚本（macOS 双击即可运行）
#
# 首次双击会被 Gatekeeper 拦截，处理方式：
#   方法 A：在 Finder 里 右键 → 打开 → 同意
#   方法 B：在终端跑一次 `chmod +x start.command && xattr -d com.apple.quarantine start.command`

set -e

# 切到脚本所在目录（即项目根目录）
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 颜色
GREEN="\033[32m"
DIM="\033[2m"
RESET="\033[0m"

echo ""
echo -e "${GREEN}▍ Verbatim · 启动中${RESET}"
echo -e "${DIM}项目目录：$(pwd)${RESET}"
echo ""

# 检查虚拟环境是否存在
if [ ! -d ".venv" ]; then
  echo "⚠️  未找到虚拟环境（.venv）。"
  echo "   首次使用请先按 INSTALL.md 完成安装步骤。"
  read -p "按回车键关闭..."
  exit 1
fi

# 检查 .env 是否存在
if [ ! -f ".env" ]; then
  echo "⚠️  未找到 .env 配置文件。"
  echo "   请先 cp .env.example .env 并填入火山引擎四件套。"
  read -p "按回车键关闭..."
  exit 1
fi

# 激活 venv 并启动
source .venv/bin/activate

# 启动 uvicorn 后台 + 自动开浏览器
PORT=8000
URL="http://127.0.0.1:${PORT}"

echo "✓ 服务即将启动在 ${URL}"
echo -e "${DIM}稍后会自动打开浏览器；窗口保持打开，关闭即停止服务。${RESET}"
echo ""

# 2 秒后自动打开浏览器
( sleep 2 && open "$URL" ) &

# 前台运行 uvicorn（Ctrl+C 退出）
uvicorn app.main:app --host 127.0.0.1 --port "$PORT"
