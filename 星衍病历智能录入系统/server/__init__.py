"""
星衍AI · 前后端分离后端服务（FastAPI）

启动方式：
    python -m server              # 直接运行
    uvicorn server:app --host 0.0.0.0 --port 8765  # 通过 uvicorn
    from app_server import app   # 向后兼容
"""
import os
import sys
import json
import time
import re
import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address

from server.singletons import get_asr
from server.middleware import auth_middleware, audit_middleware
from server.routes_auth import register_routes as register_auth_routes
from server.routes_records import register_routes as register_records_routes
from server.routes_qa import register_routes as register_qa_routes
from server.routes_templates import register_routes as register_template_routes
from server.routes_system import register_routes as register_system_routes
from server.routes_static import register_routes as register_static_routes

# ─── 日志配置 ────────────────────────────────────────────
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('audit.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('medical_record_audit')

# ─── 限流器 ─────────────────────────────────────────────
def _get_rate_limit_key(request):
    user = getattr(request.state, "user", None)
    if user and user.get("user_id"):
        return f"user:{user['user_id']}"
    return get_remote_address(request)

limiter = Limiter(key_func=_get_rate_limit_key)

# ─── FastAPI App ────────────────────────────────────────
app = FastAPI(title="星衍AI · 智能病历录入", version="2.0")
app.state.limiter = limiter

# CORS 配置
_CORS_ORIGINS_ENV = os.environ.get("XINGYAN_CORS_ORIGINS", "")
if _CORS_ORIGINS_ENV:
    ALL_ALLOWED_ORIGINS = [o.strip() for o in _CORS_ORIGINS_ENV.split(",") if o.strip()]
else:
    ALL_ALLOWED_ORIGINS = [
        "http://localhost:8765",
        "http://localhost:3000",
        "http://127.0.0.1:8765",
        "http://127.0.0.1:3000",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALL_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
    expose_headers=["Content-Type", "Authorization"],
    max_age=600,
)

# ─── 注册路由 ───────────────────────────────────────────
register_auth_routes(app, limiter)
register_records_routes(app)
register_qa_routes(app, limiter)
register_template_routes(app)
register_system_routes(app)
register_static_routes(app)

# 审计中间件（统一使用 server/middleware.py 的实现）
app.add_middleware(BaseHTTPMiddleware, dispatch=audit_middleware)

# 认证中间件：解析 JWT → 填充 request.state.user（JWT_ENFORCE=1 时未认证返回 401）
app.add_middleware(BaseHTTPMiddleware, dispatch=auth_middleware)

# ─── WebSocket ──────────────────────────────────────────

@app.websocket("/ws/asr")
async def ws_asr(websocket: WebSocket):
    """
    接收浏览器端录音的 PCM/WAV 数据，返回识别结果。
    支持流式中间识别：每累积约2秒音频发送一次 partial 结果。
    """
    # WebSocket 来源校验（本机 + 局域网，允许手机访问）
    origin = websocket.headers.get("origin", "")
    allowed_origins = [
        "http://localhost", "http://127.0.0.1",
        "http://localhost:8765", "http://127.0.0.1:8765",
        "http://localhost:3000", "http://127.0.0.1:3000",
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:8080", "http://127.0.0.1:8080",
        # 局域网段（手机浏览器访问）
        "http://192.168.", "http://10.", "http://172.16.",
        "http://172.17.", "http://172.18.", "http://172.19.",
        "http://172.2", "http://172.3",
    ]
    # 局域网 IP 段精确匹配（192.168.x.x / 10.x.x.x / 172.16-31.x.x）
    _lan_ok = any(
        origin.startswith(prefix)
        for prefix in [
            "http://192.168.", "http://10.",
            "http://172.16.", "http://172.17.", "http://172.18.", "http://172.19.",
            "http://172.20.", "http://172.21.", "http://172.22.", "http://172.23.",
            "http://172.24.", "http://172.25.", "http://172.26.", "http://172.27.",
            "http://172.28.", "http://172.29.", "http://172.30.", "http://172.31.",
        ]
    )
    if origin and not (any(origin.startswith(a) for a in allowed_origins) or _lan_ok):
        logger.warning(f"WebSocket 连接来源被拒绝: {origin}")
        return

    await websocket.accept()
    asr = get_asr()
    if asr is None:
        await websocket.send_json({"type": "error", "msg": "ASR 引擎未启用（XINGYAN_SKIP_ASR=1）"})
        await websocket.close()
        return

    audio_buffer = bytearray()
    last_partial_len = 0
    PARTIAL_THRESHOLD = 64000  # 2 秒音频
    MAX_BUFFER_SIZE = 10 * 1024 * 1024  # 10MB

    try:
        await websocket.send_json({"type": "status", "msg": "ready"})

        while True:
            msg = await websocket.receive()

            if msg.get("type") == "websocket.disconnect":
                break

            if "bytes" in msg and msg["bytes"]:
                audio_buffer.extend(msg["bytes"])
                if len(audio_buffer) > MAX_BUFFER_SIZE:
                    await websocket.send_json({"type": "error", "msg": "录音时间过长，请分段录音"})
                    audio_buffer.clear()
                    last_partial_len = 0
                    continue

                if len(audio_buffer) - last_partial_len >= PARTIAL_THRESHOLD:
                    import asyncio
                    import tempfile, wave
                    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".wav")
                    os.close(tmp_fd)
                    try:
                        with wave.open(tmp_path, 'wb') as wf:
                            wf.setnchannels(1)
                            wf.setsampwidth(2)
                            wf.setframerate(16000)
                            wf.writeframes(bytes(audio_buffer))
                        text = await asyncio.get_running_loop().run_in_executor(None, asr.transcribe_file, tmp_path)
                        if text:
                            await websocket.send_json({"type": "partial", "text": text})
                    finally:
                        try:
                            os.unlink(tmp_path)
                        except Exception:
                            pass
                    last_partial_len = len(audio_buffer)

            elif "text" in msg and msg["text"]:
                data = json.loads(msg["text"])
                cmd = data.get("cmd", "")

                if cmd == "stop":
                    if len(audio_buffer) > 3200:
                        import asyncio
                        import tempfile, wave
                        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".wav")
                        os.close(tmp_fd)
                        try:
                            with wave.open(tmp_path, 'wb') as wf:
                                wf.setnchannels(1)
                                wf.setsampwidth(2)
                                wf.setframerate(16000)
                                wf.writeframes(bytes(audio_buffer))
                            text = await asyncio.get_running_loop().run_in_executor(None, asr.transcribe_file, tmp_path)
                            await websocket.send_json({"type": "result", "text": text or ""})
                        finally:
                            try:
                                os.unlink(tmp_path)
                            except Exception:
                                pass
                    else:
                        await websocket.send_json({"type": "result", "text": ""})
                    audio_buffer.clear()
                    last_partial_len = 0

                elif cmd == "ping":
                    await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        logger.info("[Server] WebSocket 断开")
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "msg": str(e)})
        except Exception:
            pass


# ─── 导出 ───────────────────────────────────────────────
__all__ = ["app"]

# 向后兼容：app_server.py 可继续使用
# from app_server import app
