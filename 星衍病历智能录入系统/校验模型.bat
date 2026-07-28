@echo off
chcp 65001 >nul
title 星衍病历录入系统 - 模型校验
echo 正在校验语音模型...
echo.

REM 优先使用项目内 venv，否则用系统 python
if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe check_model.py
) else if exist "venv\bin\python.exe" (
    venv\bin\python.exe check_model.py
) else (
    python check_model.py
)

pause
