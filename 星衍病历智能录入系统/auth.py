#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
安全认证模块
提供 JWT Token 生成、验证、权限控制等功能
"""
import jwt
import datetime
import hashlib
import secrets
import os
from functools import wraps
from typing import Optional, Dict


# JWT 配置（生产环境必须通过环境变量注入密钥！）
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-insecure-secret-change-me")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = int(os.environ.get("JWT_EXPIRATION_HOURS", "24"))


class JWTAuth:
    """JWT 认证类"""
    
    @staticmethod
    def generate_token(user_id: int, username: str, role: str = "doctor") -> str:
        """
        生成 JWT Token
        
        Args:
            user_id: 用户ID
            username: 用户名
            role: 用户角色（doctor/admin）
        
        Returns:
            JWT Token 字符串
        """
        payload = {
            "user_id": user_id,
            "username": username,
            "role": role,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=JWT_EXPIRATION_HOURS),
            "iat": datetime.datetime.utcnow(),
        }
        
        token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
        return token
    
    @staticmethod
    def verify_token(token: str) -> Optional[Dict]:
        """
        验证 JWT Token
        
        Args:
            token: JWT Token 字符串
        
        Returns:
            解码后的 payload，验证失败返回 None
        """
        try:
            payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            print("[Auth] Token 已过期")
            return None
        except jwt.InvalidTokenError as e:
            print(f"[Auth] Token 无效: {e}")
            return None
    
    @staticmethod
    def refresh_token(token: str) -> Optional[str]:
        """
        刷新 Token（延长有效期）
        
        Args:
            token: 旧的 JWT Token
        
        Returns:
            新的 JWT Token，验证失败返回 None
        """
        payload = JWTAuth.verify_token(token)
        if not payload:
            return None
        
        # 生成新 Token
        return JWTAuth.generate_token(
            user_id=payload["user_id"],
            username=payload["username"],
            role=payload["role"]
        )


class PasswordHasher:
    """密码哈希类"""
    
    @staticmethod
    def hash_password(password: str, salt: Optional[str] = None) -> tuple:
        """
        哈希密码
        
        Args:
            password: 明文密码
            salt: 盐值（可选，不提供则自动生成）
        
        Returns:
            (hashed_password, salt) 元组
        """
        if salt is None:
            salt = secrets.token_hex(16)
        
        # 使用 SHA256 + salt
        hashed = hashlib.sha256((password + salt).encode()).hexdigest()
        return hashed, salt
    
    @staticmethod
    def verify_password(password: str, hashed: str, salt: str) -> bool:
        """
        验证密码
        
        Args:
            password: 明文密码
            hashed: 哈希后的密码
            salt: 盐值
        
        Returns:
            验证成功返回 True，否则返回 False
        """
        new_hashed, _ = PasswordHasher.hash_password(password, salt)
        return new_hashed == hashed


def require_auth(func):
    """
    需要认证的装饰器
    
    使用方法：
    @app.get("/api/protected")
    @require_auth
    async def protected_endpoint(request: Request):
        user = request.state.user
        return {"user": user}
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        from fastapi import Request, HTTPException
        from fastapi.responses import JSONResponse
        
        # 获取 request 对象
        request = None
        for arg in args:
            if isinstance(arg, Request):
                request = arg
                break
        
        if not request:
            raise HTTPException(status_code=500, detail="Request object not found")
        
        # 获取 Token
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="未提供认证令牌")
        
        token = auth_header.split(" ")[1]
        
        # 验证 Token
        payload = JWTAuth.verify_token(token)
        if not payload:
            raise HTTPException(status_code=401, detail="认证令牌无效或已过期")
        
        # 将用户信息附加到 request
        request.state.user = payload
        
        # 调用原始函数
        return await func(*args, **kwargs)
    
    return wrapper


def require_admin(func):
    """
    需要管理员权限的装饰器
    
    使用方法：
    @app.delete("/api/users/{user_id}")
    @require_admin
    async def delete_user(user_id: int, request: Request):
        user = request.state.user
        if user["role"] != "admin":
            raise HTTPException(status_code=403, detail="权限不足")
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        from fastapi import Request, HTTPException
        
        # 获取 request 对象
        request = None
        for arg in args:
            if isinstance(arg, Request):
                request = arg
                break
        
        if not request:
            raise HTTPException(status_code=500, detail="Request object not found")
        
        # 检查用户角色
        if not hasattr(request.state, "user") or request.state.user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="需要管理员权限")
        
        # 调用原始函数
        return await func(*args, **kwargs)
    
    return wrapper


# 便捷函数
def create_token(user_id: int, username: str, role: str = "doctor") -> str:
    """创建 Token 的便捷函数"""
    return JWTAuth.generate_token(user_id, username, role)


def verify_token(token: str) -> Optional[Dict]:
    """验证 Token 的便捷函数"""
    return JWTAuth.verify_token(token)


if __name__ == "__main__":
    # 测试
    print("=== JWT 认证测试 ===")
    
    # 生成 Token
    token = create_token(user_id=1, username="test_user", role="doctor")
    print(f"生成的 Token: {token[:50]}...")
    
    # 验证 Token
    payload = verify_token(token)
    print(f"验证结果: {payload}")
    
    # 刷新 Token
    new_token = JWTAuth.refresh_token(token)
    print(f"刷新后的 Token: {new_token[:50]}...")
    
    # 密码哈希测试
    print("\n=== 密码哈希测试 ===")
    password = "test_password_123"
    hashed, salt = PasswordHasher.hash_password(password)
    print(f"原始密码: {password}")
    print(f"哈希密码: {hashed}")
    print(f"盐值: {salt}")
    
    # 验证密码
    is_valid = PasswordHasher.verify_password(password, hashed, salt)
    print(f"密码验证: {'成功' if is_valid else '失败'}")
    
    # 错误密码验证
    is_valid = PasswordHasher.verify_password("wrong_password", hashed, salt)
    print(f"错误密码验证: {'成功' if is_valid else '失败'}")
