"""密码哈希与 HMAC 签名令牌（不引入第三方 JWT 库）。"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path

PBKDF2_ITERATIONS = 120_000


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def hash_password(password: str, *, iterations: int = PBKDF2_ITERATIONS, salt: bytes | None = None) -> str:
    if len(password) < 8:
        raise ValueError("密码至少 8 位")
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return f"pbkdf2${iterations}${_b64e(salt)}${_b64e(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iterations, salt, digest = stored.split("$")
        if algo != "pbkdf2":
            return False
        calc = hashlib.pbkdf2_hmac("sha256", password.encode(), _b64d(salt), int(iterations))
        return hmac.compare_digest(calc, _b64d(digest))
    except (ValueError, TypeError):
        return False


class TokenSigner:
    def __init__(self, secret: bytes, ttl_seconds: int = 7 * 24 * 3600) -> None:
        if len(secret) < 16:
            raise ValueError("签名密钥至少 16 字节")
        self.secret = secret
        self.ttl_seconds = ttl_seconds

    def issue(self, user_id: int) -> str:
        payload = {"sub": user_id, "exp": int(time.time()) + self.ttl_seconds}
        body = _b64e(json.dumps(payload, separators=(",", ":")).encode())
        signature = _b64e(hmac.new(self.secret, body.encode(), hashlib.sha256).digest())
        return f"{body}.{signature}"

    def verify(self, token: str) -> int | None:
        try:
            body, signature = token.split(".", 1)
        except ValueError:
            return None
        expected = _b64e(hmac.new(self.secret, body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(expected, signature):
            return None
        try:
            payload = json.loads(_b64d(body))
        except (ValueError, TypeError):
            return None
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        return int(payload["sub"])


def load_secret(path: Path) -> bytes:
    """优先环境变量，其次本地密钥文件（首次自动生成）。"""
    env = os.environ.get("QPQUIZ_SECRET")
    if env:
        return env.encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return path.read_bytes()
    secret = secrets.token_bytes(32)
    path.write_bytes(secret)
    path.chmod(0o600)
    return secret
