"""test_main.py Tests for FastAPI app: error handlers, API endpoints, and archived report retrieval."""

from __future__ import annotations

import json

import pytest
from starlette.requests import Request
from starlette.testclient import TestClient

import app.main as main_module
from app.services.core.llm_service import LLMConfigurationError
from app.services.core.report_service import ResearchWorkflowError
from app.models.research_models import ReportArchiveSummary, ResearchReport


def _build_request() -> Request:
    """Build a minimal Starlette Request for testing error handlers."""
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/research",
            "headers": [],
        }
    )


# ---------------------------------------------------------------------------
# Error handler tests
# ---------------------------------------------------------------------------


class TestErrorHandler:
    """Tests for FastAPI exception handlers."""

    def test_handle_api_error_returns_llm_config_error(self):
        """LLMConfigurationError should return a 503 with structured error body."""
        request = _build_request()
        response = main_module.handle_api_error(request, LLMConfigurationError())

        assert response.status_code == 503
        body = json.loads(response.body.decode("utf-8"))
        assert body["error_code"] == "llm_config_missing"
        assert body["title"] == "模型配置缺失"

    def test_handle_api_error_returns_workflow_error(self):
        """ResearchWorkflowError should return a 502 with structured error body."""
        request = _build_request()
        response = main_module.handle_api_error(
            request,
            ResearchWorkflowError(
                detail="No papers found.",
                suggestion="Try a broader topic.",
            ),
        )

        assert response.status_code == 502
        body = json.loads(response.body.decode("utf-8"))
        assert body["error_code"] == "research_workflow_failed"
        assert body["detail"] == "No papers found."
        assert body["suggestion"] == "Try a broader topic."


# ---------------------------------------------------------------------------
# Health check tests
# ---------------------------------------------------------------------------


class TestHealthCheck:
    """Tests for the /health endpoint."""

    def test_health_check_returns_ok(self):
        """Health check should return 200 with status ok and diagnostics."""
        client = TestClient(main_module.app)
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "app" in data
        assert data["version"] == "2.0.0"
        assert "llm_enabled" in data
        assert "search_cache_size" in data


# ---------------------------------------------------------------------------
# Archived reports API tests
# ---------------------------------------------------------------------------


class TestListArchivedReports:
    """Tests for the GET /api/v1/reports endpoint."""

    def test_list_archived_reports_returns_history(self, monkeypatch):
        """Should return a list of ReportArchiveSummary."""
        monkeypatch.setattr(
            main_module.report_archive_service,
            "list_reports",
            lambda limit: [
                ReportArchiveSummary(
                    report_id="report-1",
                    topic="Test topic",
                    created_at="2026-06-01T12:00:00",
                    paper_count=3,
                    stage_count=12,
                    support_score=0.9,
                    verdict="overall_pass",
                )
            ],
        )

        client = TestClient(main_module.app)
        response = client.get("/api/v1/reports", params={"limit": 12})
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["report_id"] == "report-1"

    def test_list_archived_reports_empty(self, monkeypatch):
        """Should return empty list when no reports exist."""
        monkeypatch.setattr(
            main_module.report_archive_service,
            "list_reports",
            lambda limit: [],
        )

        client = TestClient(main_module.app)
        response = client.get("/api/v1/reports")
        assert response.status_code == 200
        assert response.json() == []


class TestGetArchivedReport:
    """Tests for the GET /api/v1/reports/{report_id} endpoint."""

    def test_get_archived_report_returns_report(self, monkeypatch):
        """Should return the full ResearchReport for a valid report_id."""
        monkeypatch.setattr(
            main_module.report_archive_service,
            "get_report",
            lambda report_id: ResearchReport.model_validate(
                {
                    "request": {"topic": "Test topic", "max_papers": 3, "include_memory": True, "enable_full_text": False, "max_full_text_papers": 2},
                    "clarification": {
                        "clarified_topic": "Test topic",
                        "research_goal": "Verify retrieval",
                        "scope": "Test scope",
                        "constraints": [],
                    },
                    "brief": {"topic": "Test topic", "objective": "Verify retrieval"},
                    "plan": {"normalized_topic": "Test topic", "search_keywords": ["test"], "focus_areas": ["test"], "output_sections": ["Overview"]},
                    "papers": [],
                    "full_text_documents": [],
                    "insights": [],
                    "evidence_bundles": [],
                    "claim_evidence_table": [],
                    "gap_report": {"reasoning": "Test."},
                    "comparison": {"overview": "Test overview."},
                    "citation_verification": {"overall_score": 0.8, "supported_count": 1, "unsupported_count": 0, "items": []},
                    "review_report": {"verdict": "overall_pass"},
                    "stage_history": [],
                    "research_note": "Test note.",
                    "next_actions": [],
                }
            ),
        )

        client = TestClient(main_module.app)
        response = client.get("/api/v1/reports/report-1")
        assert response.status_code == 200
        data = response.json()
        assert data["request"]["topic"] == "Test topic"

    def test_get_archived_report_returns_404_for_missing(self, monkeypatch):
        """Should return 404 when report_id is not found."""
        from app.api_error import ArchivedReportNotFoundError

        def raise_not_found(report_id):
            raise ArchivedReportNotFoundError(report_id)

        monkeypatch.setattr(
            main_module.report_archive_service,
            "get_report",
            raise_not_found,
        )

        client = TestClient(main_module.app)
        response = client.get("/api/v1/reports/nonexistent")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Validation error tests
# ---------------------------------------------------------------------------


class TestValidation:
    """Tests for request validation."""

    def test_research_endpoint_rejects_missing_topic(self):
        """POST /api/v1/research should reject a request without topic field."""
        client = TestClient(main_module.app)
        response = client.post("/api/v1/research", json={"max_papers": 1})
        assert response.status_code == 422

    def test_research_endpoint_rejects_invalid_max_papers(self):
        """POST /api/v1/research should reject max_papers outside allowed range."""
        client = TestClient(main_module.app)
        response = client.post("/api/v1/research", json={"topic": "test", "max_papers": 0})
        assert response.status_code == 422

        response = client.post("/api/v1/research", json={"topic": "test", "max_papers": 100})
        assert response.status_code == 422

    def test_research_endpoint_rejects_wrong_type(self):
        """POST /api/v1/research should reject non-string topic."""
        client = TestClient(main_module.app)
        response = client.post("/api/v1/research", json={"topic": 123, "max_papers": 1})
        assert response.status_code == 422


class TestResearchStreamCapacity:
    """TestResearchStreamCapacity 流式研究任务容量保护测试。"""

    def test_stream_research_returns_429_when_registry_is_full(self, monkeypatch):
        """test_stream_research_returns_429_when_registry_is_full 注册表满载时返回结构化 429。"""
        from app.api_error import ActiveTaskLimitExceededError

        class _FullRegistry:
            def create_task(self, request):
                raise ActiveTaskLimitExceededError(max_active_tasks=1)

        monkeypatch.setattr(main_module, "get_task_registry", lambda: _FullRegistry())

        client = TestClient(main_module.app)
        response = client.post("/api/v1/research/stream", json={"topic": "test", "max_papers": 1})

        assert response.status_code == 429
        data = response.json()
        assert data["error_code"] == "too_many_active_tasks"
