@echo off
chcp 65001 >nul
echo ========================================
echo   星衍AI智能病历录入系统 - 一键启动脚本
echo ========================================
echo.

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python，请先安装 Python 3.8+
    echo 下载地址：https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/3] 检查依赖...
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [错误] 依赖安装失败，请检查网络连接
    pause
    exit /b 1
)

echo [2/3] 检查语音模型...
if not exist "model" (
    echo [提示] 未检测到语音模型目录
    echo.
    echo 请下载 Vosk 中文模型并解压到 model 目录：
    echo   小模型(40MB): https://alphacephei.com/vosk/models/vosk-model-small-cn-0.22.zip
    echo   大模型(1.8GB): https://alphacephei.com/vosk/models/vosk-model-cn-0.22.zip
    echo.
    echo 下载后把解压后的文件夹重命名为 model，放在与本脚本相同的目录下
    echo.
    pause
    exit /b 1
)

echo [3/3] 启动程序...
python main.py

if errorlevel 1 (
    echo.
    echo [错误] 程序运行失败
    pause
)
