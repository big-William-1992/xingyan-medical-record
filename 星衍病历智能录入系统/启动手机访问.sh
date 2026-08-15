#!/bin/bash
# 星衍AI · 手机端启动脚本
# 启动后端服务并显示局域网访问地址

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 激活虚拟环境
source venv/bin/activate 2>/dev/null

# 获取本机局域网IP
get_local_ip() {
    # macOS
    if command -v ipconfig &>/dev/null; then
        ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null
    fi
    # Linux
    if command -v hostname &>/dev/null; then
        hostname -I 2>/dev/null | awk '{print $1}'
    fi
}

LOCAL_IP=$(get_local_ip)
PORT=8765

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║     星衍AI · 智能病历录入 - 手机访问        ║"
echo "╠══════════════════════════════════════════════╣"
echo "║                                              ║"
echo "║  📱 手机浏览器访问：                         ║"
echo "║                                              ║"
if [ -n "$LOCAL_IP" ]; then
echo "║     http://${LOCAL_IP}:${PORT}               "
else
echo "║     http://localhost:${PORT}                  "
echo "║     （未检测到局域网IP，请手动查看）          ║"
fi
echo "║                                              ║"
echo "║  💡 提示：                                   ║"
echo "║     • 手机和电脑需连接同一WiFi               ║"
echo "║     • 建议添加到手机主屏幕                   ║"
echo "║     • 按 Ctrl+C 停止服务                     ║"
echo "║                                              ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# 启动服务
python app_server.py
