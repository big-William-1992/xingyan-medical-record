"""
认证路由：登录 + JWT Token
"""
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi import Body
from slowapi.errors import RateLimitExceeded

from server.singletons import get_db
from server.middleware import (
    check_login_attempts, record_login_failure,
    clear_login_failures,
)
from auth import create_token
import time


def register_routes(app, limiter):
    """注册认证路由（登录限流由 middleware 手动锁定机制负责，不叠加 slowapi）"""

    @app.post("/api/auth/login")
    async def auth_login(request: Request, body: dict = Body(...)):
        """用户名密码登录，返回 JWT Token"""
        username = (body.get("username") or "").strip()
        password = body.get("password") or ""
        if not username or not password:
            return {"ok": False, "msg": "用户名和密码不能为空"}

        # 检查账号锁定（5 次失败锁 5 分钟）
        locked = check_login_attempts(username)
        if locked:
            return {"ok": False, "msg": f"登录失败过多，请 {locked['remaining']} 秒后再试"}

        db = get_db()
        user = db.verify_user(username, password)
        if not user:
            record_login_failure(username)
            return {"ok": False, "msg": "用户名或密码错误"}

        clear_login_failures(username)
        token = create_token(
            user_id=user["id"],
            username=user["username"],
            role=user.get("role", "doctor"),
        )
        return {"ok": True, "token": token, "user": user}

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
        return JSONResponse(
            status_code=429,
            content={"detail": "请求过于频繁，请稍后再试"},
        )
