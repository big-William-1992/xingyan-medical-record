#!/bin/bash
# 星衍AI智能病历录入系统 - Mac 启动脚本

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 激活虚拟环境
source venv/bin/activate

# 设置 Qt 插件路径
# 注意：QT_QPA_PLATFORM_PLUGIN_PATH 必须指向含 libqcocoa.dylib 的 platforms 目录，
# 否则在含中文字符的路径下 Qt 无法定位 cocoa 插件而报错退出。
export QT_QPA_PLATFORM_PLUGIN_PATH="$SCRIPT_DIR/venv/lib/python3.14/site-packages/PyQt5/Qt5/plugins/platforms"
# 同时设置插件根目录，兼容其他插件（styles/imageformats 等）
export QT_PLUGIN_PATH="$SCRIPT_DIR/venv/lib/python3.14/site-packages/PyQt5/Qt5/plugins"

# 修复 macOS 输入法兼容性问题
export QT_IM_MODULE=

# 启动程序
python main.py
