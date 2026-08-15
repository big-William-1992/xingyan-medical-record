#!/bin/bash
# ═══════════════════════════════════════════════════
# 星衍AI · 智能病历录入系统 — 打包脚本 (macOS/Linux)
# 用法: bash build.sh
# 输出: dist/星衍AI病历录入/ (文件夹) 或 dist/星衍AI病历录入.app (macOS)
# ═══════════════════════════════════════════════════

set -e

echo "╔══════════════════════════════════════════════╗"
echo "║  星衍AI · 打包构建                            ║"
echo "╚══════════════════════════════════════════════╝"

# 确保在项目目录
cd "$(dirname "$0")"

# 检查 Python 环境
if [ -d "venv" ]; then
    source venv/bin/activate
    echo "✅ 已激活 venv"
else
    echo "⚠️  未找到 venv，使用系统 Python"
fi

# 检查依赖
echo "📦 检查依赖..."
pip install -q pyinstaller pywebview fastapi uvicorn 2>/dev/null || true

# 清理旧构建
echo "🧹 清理旧构建..."
rm -rf build/ dist/

# 执行打包
echo "🔨 开始打包..."
pyinstaller build.spec --noconfirm

# 检查结果
if [ -d "dist/星衍AI病历录入" ]; then
    echo ""
    echo "✅ 打包成功！"
    echo "   输出目录: dist/星衍AI病历录入/"
    echo ""
    if [ "$(uname)" = "Darwin" ] && [ -d "dist/星衍AI病历录入.app" ]; then
        echo "   macOS App: dist/星衍AI病历录入.app"
        echo "   双击 .app 即可运行"
    else
        echo "   可执行文件: dist/星衍AI病历录入/星衍AI病历录入"
        echo "   运行: ./dist/星衍AI病历录入/星衍AI病历录入"
    fi
    echo ""
    echo "📦 压缩为 zip（方便分发）..."
    cd dist
    zip -r "星衍AI病历录入-$(uname -s)-$(uname -m).zip" "星衍AI病历录入"* 2>/dev/null || true
    cd ..
    echo "✅ 完成！zip 文件在 dist/ 目录"
else
    echo "❌ 打包失败，请检查错误信息"
    exit 1
fi
