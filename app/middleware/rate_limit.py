"""rate_limit 简单的内存滑动窗口限流中间件。"""

from __future__ import annotations

import logging
import threading
import time
from typing import Dict, List, Tuple

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """RateLimitMiddleware 按 IP 限制研究类请求频率。"""

    def __init__(
        self,
        app,
        max_requests: int = 3,
        window_seconds: int = 60,
    ) -> None:
        super().__init__(app)
        self._max = max_requests
        self._window = window_seconds
        self._store: Dict[str, List[float]] = {}
        self._lock = threading.Lock()

    def _is_limited(self, client_ip: str) -> bool:
        now = time.monotonic()
        cutoff = now - self._window
        with self._lock:
            timestamps = self._store.get(client_ip, [])
            timestamps = [ts for ts in timestamps if ts > cutoff]
            if len(timestamps) >= self._max:
                self._store[client_ip] = timestamps
                return True
            timestamps.append(now)
            self._store[client_ip] = timestamps
            return False

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method == "POST" and "/api/v1/research/stream" in request.url.path:
            client_ip = request.client.host if request.client else "unknown"
            if self._is_limited(client_ip):
                logger.info("RateLimitMiddleware blocked, ip=%s, path=%s", client_ip, request.url.path)
                return Response(
                    content='{"error_code":"rate_limited","title":"请求过于频繁","detail":"请稍后再试。","suggestion":"研究任务每分钟最多提交 3 次。"}',
                    status_code=429,
                    media_type="application/json",
                )
        return await call_next(request)
