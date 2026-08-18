"""
单元测试：auth.py - JWT 生成/验证 + 密码哈希
"""
import pytest
import jwt
import datetime


class TestJWT:
    """JWT Token 测试"""

    def test_generate_token(self):
        from auth import JWTAuth, JWT_SECRET_KEY
        token = JWTAuth.generate_token(1, "testuser", "doctor")
        assert isinstance(token, str)
        assert len(token) > 0

    def test_token_has_exp(self):
        from auth import JWTAuth, JWT_SECRET_KEY
        token = JWTAuth.generate_token(1, "testuser", "doctor")
        payload = jwt.decode(
            token, JWT_SECRET_KEY,
            algorithms=["HS256"],
            audience="xingyan-api",
            options={"verify_exp": False},
        )
        assert "exp" in payload
        assert "iat" in payload
        assert payload["exp"] > payload["iat"]

    def test_token_expiry_default_24h(self):
        """默认 JWT 过期时间 24 小时"""
        from auth import JWTAuth, JWT_SECRET_KEY, JWT_EXPIRATION_HOURS
        assert JWT_EXPIRATION_HOURS == 24
        token = JWTAuth.generate_token(1, "testuser", "doctor")
        payload = jwt.decode(
            token, JWT_SECRET_KEY,
            algorithms=["HS256"],
            audience="xingyan-api",
            options={"verify_exp": False},
        )
        delta = payload["exp"] - payload["iat"]
        assert delta == 24 * 3600

    def test_verify_valid_token(self):
        from auth import JWTAuth, JWT_SECRET_KEY
        token = JWTAuth.generate_token(1, "testuser", "doctor")
        payload = JWTAuth.verify_token(token)
        assert payload is not None
        assert payload["user_id"] == 1
        assert payload["username"] == "testuser"
        assert payload["role"] == "doctor"

    def test_verify_invalid_token(self):
        from auth import verify_token
        assert verify_token("invalid.token.here") is None

    def test_refresh_token(self):
        from auth import JWTAuth, JWT_SECRET_KEY
        token = JWTAuth.generate_token(1, "testuser", "doctor")
        new_token = JWTAuth.refresh_token(token)
        assert new_token is not None
        # 新 token 验证通过且用户信息一致
        payload = JWTAuth.verify_token(new_token)
        assert payload is not None
        assert payload["user_id"] == 1
        assert payload["username"] == "testuser"


class TestPasswordHasher:
    """密码哈希测试"""

    def test_hash_password(self):
        from auth import PasswordHasher
        hashed, salt = PasswordHasher.hash_password("testpass123")
        assert len(hashed) == 64  # SHA256 hex
        assert len(salt) == 32    # 16 bytes hex

    def test_verify_correct_password(self):
        from auth import PasswordHasher
        hashed, salt = PasswordHasher.hash_password("testpass123")
        assert PasswordHasher.verify_password("testpass123", hashed, salt) is True

    def test_verify_wrong_password(self):
        from auth import PasswordHasher
        hashed, salt = PasswordHasher.hash_password("testpass123")
        assert PasswordHasher.verify_password("wrongpass", hashed, salt) is False
