#!/bin/bash
# 星衍AI智能病历录入系统 - Mac 启动脚本

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 激活虚拟环境
source venv/bin/activate

# 设置 Qt 插件路径
export QT_QPA_PLATFORM_PLUGIN_PATH="$SCRIPT_DIR/venv/lib/python3.14/site-packages/PyQt5/Qt5/plugins"

# 修复 macOS 输入法兼容性问题
export QT_IM_MODULE=

# 启动程序
python main.py
