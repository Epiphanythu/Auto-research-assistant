"""test_rate_limit.py 限流中间件测试。"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.middleware.rate_limit import RateLimitMiddleware
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route


async def _fake_stream(request):
    return JSONResponse({"status": "ok"})


def _make_app(max_requests: int = 2, window_seconds: int = 60) -> Starlette:
    app = Starlette(routes=[Route("/api/v1/research/stream", _fake_stream, methods=["POST"])])
    app.add_middleware(RateLimitMiddleware, max_requests=max_requests, window_seconds=window_seconds)
    return app


class TestRateLimitMiddleware:
    """Tests for RateLimitMiddleware."""

    def test_allows_requests_within_limit(self):
        app = _make_app(max_requests=3)
        client = TestClient(app)
        for _ in range(3):
            response = client.post("/api/v1/research/stream")
            assert response.status_code == 200

    def test_blocks_requests_exceeding_limit(self):
        app = _make_app(max_requests=2)
        client = TestClient(app)
        client.post("/api/v1/research/stream")
        client.post("/api/v1/research/stream")
        response = client.post("/api/v1/research/stream")
        assert response.status_code == 429
        assert "rate_limited" in response.text

    def test_non_research_paths_not_limited(self):
        async def _other(request):
            return JSONResponse({"ok": True})

        app = Starlette(routes=[
            Route("/api/v1/other", _other, methods=["POST"]),
            Route("/api/v1/research/stream", _fake_stream, methods=["POST"]),
        ])
        app.add_middleware(RateLimitMiddleware, max_requests=1, window_seconds=60)
        client = TestClient(app)
        # Exhaust the limit on research endpoint
        client.post("/api/v1/research/stream")
        # Other endpoint should still work
        response = client.post("/api/v1/other")
        assert response.status_code == 200

    def test_429_response_body_is_structured(self):
        app = _make_app(max_requests=1)
        client = TestClient(app)
        client.post("/api/v1/research/stream")
        response = client.post("/api/v1/research/stream")
        assert response.status_code == 429
        data = response.json()
        assert data["error_code"] == "rate_limited"
        assert "title" in data
