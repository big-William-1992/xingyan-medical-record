"""
中间件：认证、限流、审计
"""
import os
import time
import threading
import re as _re
from typing import Optional

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
import jwt
import logging

# 统一从 auth.py 读取 JWT 配置（单一事实源，避免密钥分裂）
from auth import JWT_SECRET_KEY, JWT_ALGORITHM, JWT_EXPIRATION_HOURS

logger = logging.getLogger('medical_record_audit')

# ─── 登录失败计数器 ─────────────────────────────────────
_login_attempts = {}
_login_attempts_lock = threading.Lock()
_login_lock_max = 5
_login_lock_secs = 300
# 锁定记录最大保留数（防内存无限增长）
_login_attempts_max = 10000


# 强制认证开关：默认关闭（局域网/本地部署无需登录），生产环境显式开启
JWT_ENFORCE = os.environ.get("XINGYAN_JWT_ENFORCE", "0") == "1"


async def auth_middleware(request: Request, call_next):
    """
    认证中间件：解析 Authorization Bearer Token → 填充 request.state.user
    - 携带有效 Token：解析出 user_id/username/role
    - 未携带 Token：
      · JWT_ENFORCE=1（生产）：返回 401
      · 默认（局域网）：使用默认用户 user_id=1（兼容现有前端）
    """
    request.state.user = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            payload = jwt.decode(
                auth_header[7:],
                JWT_SECRET_KEY,
                algorithms=[JWT_ALGORITHM],
                options={"verify_exp": True},
            )
            request.state.user = {
                "user_id": payload.get("user_id", 1),
                "username": payload.get("username", ""),
                "role": payload.get("role", "doctor"),
            }
        except jwt.ExpiredSignatureError:
            if JWT_ENFORCE:
                return JSONResponse(status_code=401, content={"detail": "Token 已过期，请重新登录"})
        except Exception as e:
            logger.warning(f"[Auth] Token 解析失败: {e}")

    if request.state.user is None:
        if JWT_ENFORCE:
            return JSONResponse(status_code=401, content={"detail": "未认证，请登录"})
        request.state.user = {"user_id": 1, "username": "默认用户", "role": "doctor"}

    return await call_next(request)


def get_current_user(request: Request) -> dict:
    """获取当前用户（由认证中间件填充，未填充时回退默认用户）"""
    user = getattr(request.state, "user", None)
    if user:
        return user
    return {"user_id": 1, "username": "默认用户", "role": "doctor"}


def require_admin(request: Request):
    """需要管理员权限（先确保已认证）"""
    user = get_current_user(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


def check_login_attempts(username: str) -> Optional[dict]:
    """检查账号是否被临时锁定，返回剩余秒数或 None"""
    with _login_attempts_lock:
        info = _login_attempts.get(username)
        if info and time.time() < info.get("until", 0):
            return {"remaining": int(info["until"] - time.time())}
        if info:
            _login_attempts.pop(username, None)
    return None


def record_login_failure(username: str):
    """记录登录失败（锁内用新 dict 替换，避免原地修改竞态）"""
    with _login_attempts_lock:
        # 防内存无限增长：超限时清理已过期的记录
        if len(_login_attempts) >= _login_attempts_max:
            now = time.time()
            expired = [k for k, v in _login_attempts.items() if v.get("until", 0) <= now]
            for k in expired:
                _login_attempts.pop(k, None)
            # 仍超限则清空最旧的一半
            if len(_login_attempts) >= _login_attempts_max:
                _login_attempts.clear()

        info = _login_attempts.get(username, {"count": 0, "until": 0})
        new_count = info.get("count", 0) + 1
        new_until = info.get("until", 0)
        if new_count >= _login_lock_max:
            new_until = time.time() + _login_lock_secs
        _login_attempts[username] = {"count": new_count, "until": new_until}


def clear_login_failures(username: str):
    """登录成功后清除失败计数"""
    with _login_attempts_lock:
        _login_attempts.pop(username, None)


async def audit_middleware(request: Request, call_next):
    """审计中间件：记录所有 API 请求"""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time

    safe_path = _re.sub(r'/\d+', '/*', request.url.path)
    logger.info(
        f"{request.method} {safe_path} - "
        f"Status: {response.status_code} - "
        f"Client: {request.client.host} - "
        f"Time: {process_time:.3f}s"
    )
    return response
