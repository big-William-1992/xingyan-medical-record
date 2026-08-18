"""
静态文件路由（前端页面 + JS 资源）
"""
from fastapi import Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
FRONTEND_DIR.mkdir(exist_ok=True)


def register_routes(app):
    """注册静态文件路由"""

    @app.get("/")
    async def index():
        return FileResponse(FRONTEND_DIR / "index.html")

    # sherpa-onnx WASM 离线语音识别资源（引擎 + 模型，用 download_offline_asr.py 下载）
    wasm_dir = FRONTEND_DIR / "wasm"
    if wasm_dir.exists():
        app.mount("/wasm", StaticFiles(directory=str(wasm_dir)), name="wasm")

    @app.get("/audio-processor.js")
    async def serve_audio_processor():
        return FileResponse(FRONTEND_DIR / "audio-processor.js", media_type="application/javascript")

    @app.get("/offline.js")
    async def serve_offline_js():
        return FileResponse(FRONTEND_DIR / "offline.js", media_type="application/javascript")

    @app.get("/offline-asr.js")
    async def serve_offline_asr_js():
        return FileResponse(FRONTEND_DIR / "offline-asr.js", media_type="application/javascript")

    @app.get("/service-worker.js")
    async def serve_service_worker():
        return FileResponse(FRONTEND_DIR / "service-worker.js", media_type="application/javascript")
