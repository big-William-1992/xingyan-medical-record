#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
星衍AI · 智能病历录入系统 — GUI 启动器
使用 pywebview 创建原生桌面窗口，内嵌 FastAPI 后端 + Web 前端
打包后可生成 .exe (Windows) / .app (macOS) / 可执行文件 (Linux)

启动方式:
  python gui_launcher.py          # 正常启动
  python gui_launcher.py --debug  # 调试模式（显示开发者工具）
"""
import sys
import os
import threading
import time
import socket
import webbrowser

# 确保工作目录正确
if getattr(sys, 'frozen', False):
    # PyInstaller 打包后
    BASE_DIR = os.path.dirname(sys.executable)
    # 打包时数据文件在 _MEIPASS 中
    RESOURCE_DIR = getattr(sys, '_MEIPASS', BASE_DIR)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    RESOURCE_DIR = BASE_DIR

os.chdir(BASE_DIR)
sys.path.insert(0, BASE_DIR)

# ─── 配置 ───
HOST = "127.0.0.1"
PORT = 8765
WINDOW_TITLE = "星衍AI · 智能病历录入系统 v2.0"
WINDOW_WIDTH = 1400
WINDOW_HEIGHT = 900
DEBUG = "--debug" in sys.argv


def find_free_port(start=8765, end=8800):
    """找一个可用端口"""
    for port in range(start, end):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind((HOST, port))
                return port
        except OSError:
            continue
    return start


def start_server(port):
    """在后台线程启动 FastAPI 服务器"""
    import uvicorn
    from app_server import app

    config = uvicorn.Config(
        app,
        host=HOST,
        port=port,
        log_level="warning" if not DEBUG else "info",
        access_log=False,
    )
    server = uvicorn.Server(config)
    server.run()


def wait_for_server(port, timeout=15):
    """等待服务器就绪"""
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((HOST, port))
                return True
        except (ConnectionRefusedError, OSError):
            time.sleep(0.2)
    return False


def main():
    import webview

    port = find_free_port()
    url = f"http://{HOST}:{port}"

    print(f"""
    ╔══════════════════════════════════════════════╗
    ║  星衍AI · 智能病历录入系统                    ║
    ║  启动中... 端口: {port}                       ║
    ╚══════════════════════════════════════════════╝
    """)

    # 后台启动 FastAPI
    server_thread = threading.Thread(target=start_server, args=(port,), daemon=True)
    server_thread.start()

    # 等待服务器就绪
    if not wait_for_server(port):
        print("❌ 服务器启动超时，尝试用浏览器打开...")
        webbrowser.open(url)
        sys.exit(1)

    print(f"✅ 服务器就绪: {url}")

    # 创建原生窗口
    window = webview.create_window(
        title=WINDOW_TITLE,
        url=url,
        width=WINDOW_WIDTH,
        height=WINDOW_HEIGHT,
        min_size=(1024, 700),
        resizable=True,
        text_select=True,
    )

    # 启动 pywebview（阻塞直到窗口关闭）
    webview.start(
        debug=DEBUG,
        gui=None,  # 自动选择最佳后端
    )

    print("👋 窗口已关闭，退出。")


if __name__ == "__main__":
    main()
