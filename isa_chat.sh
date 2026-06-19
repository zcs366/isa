#!/bin/bash
# ISA Chat — 启动脚本
# 用法: ./isa_chat.sh              → 进入TUI（默认main频道）
#       ./isa_chat.sh channel名    → CLI看消息
#       ./isa_chat.sh channel名 消息 → CLI发消息

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ $# -eq 0 ]; then
    # 无参数 → TUI模式
    python3 -c "import rich" 2>/dev/null || pip install rich -q
    echo "📡 ISA Chat TUI 启动中..."
    exec python3 "$SCRIPT_DIR/isa_chat.py"
elif [ $# -eq 1 ]; then
    # 一个参数 → 只看消息
    exec python3 "$SCRIPT_DIR/isa_chat.py" "$1"
else
    # 两个参数 → 发消息
    exec python3 "$SCRIPT_DIR/isa_chat.py" "$1" "${@:2}"
fi
