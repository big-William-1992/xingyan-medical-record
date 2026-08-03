@echo off
REM ═══════════════════════════════════════════════════
REM 星衍AI · 智能病历录入系统 — 打包脚本 (Windows)
REM 用法: build.bat
REM 输出: dist\星衍AI病历录入\ (文件夹，含 .exe)
REM ═══════════════════════════════════════════════════

echo ╔══════════════════════════════════════════════╗
echo ║  星衍AI · 打包构建 (Windows)                  ║
echo ╚══════════════════════════════════════════════╝

cd /d "%~dp0"

REM 激活虚拟环境
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    echo ✅ 已激活 venv
) else (
    echo ⚠️  未找到 venv，使用系统 Python
)

REM 检查依赖
echo 📦 检查依赖...
pip install -q pyinstaller pywebview fastapi uvicorn 2>nul

REM 清理旧构建
echo 🧹 清理旧构建...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM 执行打包
echo 🔨 开始打包...
pyinstaller build.spec --noconfirm

REM 检查结果
if exist "dist\星衍AI病历录入\星衍AI病历录入.exe" (
    echo.
    echo ✅ 打包成功！
    echo    输出目录: dist\星衍AI病历录入\
    echo    可执行文件: dist\星衍AI病历录入\星衍AI病历录入.exe
    echo.
    echo 📦 压缩为 zip...
    powershell -Command "Compress-Archive -Path 'dist\星衍AI病历录入\*' -DestinationPath 'dist\星衍AI病历录入-Windows-x64.zip' -Force"
    echo ✅ 完成！zip 文件在 dist\ 目录
) else (
    echo ❌ 打包失败，请检查错误信息
    exit /b 1
)

pause
