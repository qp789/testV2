"""中间件：请求 ID / 耗时统计，以及简单的内存限流。"""

from __future__ import annotations

import time
import uuid
from collections import defaultdict

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        started = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{(time.perf_counter() - started) * 1000:.1f}ms"
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """按令牌/IP 的滑动窗口限流，默认每分钟 120 次。"""

    def __init__(self, app, limit: int = 120, window: int = 60) -> None:
        super().__init__(app)
        self.limit = limit
        self.window = window
        self._hits: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith("/api"):
            return await call_next(request)
        key = request.headers.get("Authorization") or (
            request.client.host if request.client else "anonymous"
        )
        now = time.time()
        hits = [stamp for stamp in self._hits[key] if now - stamp < self.window]
        if len(hits) >= self.limit:
            return JSONResponse({"detail": "请求过于频繁，请稍后再试"}, status_code=429)
        hits.append(now)
        self._hits[key] = hits
        return await call_next(request)
