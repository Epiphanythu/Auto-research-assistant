"""rate_limit 简单的内存滑动窗口限流中间件。"""

from __future__ import annotations

import logging
import threading
import time
from typing import Dict, List

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """RateLimitMiddleware 按 IP 限制研究类请求频率，并控制单 IP 并发上限。"""

    def __init__(
        self,
        app,
        max_requests: int = 3,
        window_seconds: int = 60,
        max_in_flight: int = 2,
    ) -> None:
        super().__init__(app)
        self._max = max_requests
        self._window = window_seconds
        self._max_in_flight = max(1, max_in_flight)
        self._store: Dict[str, List[float]] = {}
        self._in_flight: Dict[str, int] = {}
        self._lock = threading.Lock()

    def _is_window_limited(self, client_ip: str) -> bool:
        # 1. 滑动窗口：window 秒内最多 max_requests 次
        now = time.monotonic()
        cutoff = now - self._window
        with self._lock:
            timestamps = [ts for ts in self._store.get(client_ip, []) if ts > cutoff]
            if len(timestamps) >= self._max:
                self._store[client_ip] = timestamps
                return True
            timestamps.append(now)
            self._store[client_ip] = timestamps
            return False

    def _try_acquire_slot(self, client_ip: str) -> bool:
        # 2. 并发上限：同 IP 同时运行的研究任务数不超过 max_in_flight
        with self._lock:
            current = self._in_flight.get(client_ip, 0)
            if current >= self._max_in_flight:
                return False
            self._in_flight[client_ip] = current + 1
            return True

    def _release_slot(self, client_ip: str) -> None:
        with self._lock:
            current = self._in_flight.get(client_ip, 0)
            if current <= 1:
                self._in_flight.pop(client_ip, None)
            else:
                self._in_flight[client_ip] = current - 1

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # 仅对 research 流式接口做限流与并发控制
        if request.method == "POST" and "/api/v1/research/stream" in request.url.path:
            client_ip = request.client.host if request.client else "unknown"
            # 1. 频率限流
            if self._is_window_limited(client_ip):
                logger.info("RateLimitMiddleware blocked, ip=%s, path=%s", client_ip, request.url.path)
                return Response(
                    content='{"error_code":"rate_limited","title":"请求过于频繁","detail":"请稍后再试。","suggestion":"研究任务每分钟最多提交 3 次。"}',
                    status_code=429,
                    media_type="application/json",
                )
            # 2. 并发上限
            if not self._try_acquire_slot(client_ip):
                logger.info("RateLimitMiddleware concurrency blocked, ip=%s", client_ip)
                return Response(
                    content='{"error_code":"too_many_in_flight","title":"并行任务过多","detail":"当前 IP 已有研究任务在运行。","suggestion":"请等待已有任务完成后再提交新任务。"}',
                    status_code=429,
                    media_type="application/json",
                )
            try:
                return await call_next(request)
            finally:
                self._release_slot(client_ip)
        return await call_next(request)
