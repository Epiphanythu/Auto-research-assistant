"""test_report_archive_service.py Tests for ReportArchiveService: save, list, get, and index persistence."""

from __future__ import annotations

import json

import pytest

from app.models.research_models import (
    ClarificationResult,
    ComparisonSummary,
    GapReport,
    ResearchBrief,
    ResearchPlan,
    ResearchReport,
    ResearchRequest,
    ReviewReport,
    SynthesisReliability,
)
from app.services.infrastructure.report_archive_service import ReportArchiveService


def _build_report() -> ResearchReport:
    """Build a minimal valid ResearchReport for testing."""
    return ResearchReport(
        request=ResearchRequest(topic="test archive", max_papers=2),
        clarification=ClarificationResult(
            clarified_topic="test archive",
            research_goal="Verify archive flow.",
            scope="Test scope",
        ),
        brief=ResearchBrief(topic="test archive", objective="Verify archive flow."),
        plan=ResearchPlan(
            normalized_topic="test archive",
            search_keywords=["test archive"],
            focus_areas=["archive"],
            output_sections=["Overview"],
        ),
        papers=[],
        insights=[],
        evidence_bundles=[],
        gap_report=GapReport(reasoning="Current version for testing."),
        comparison=ComparisonSummary(overview="Test overview."),
        review_report=ReviewReport(verdict="overall_pass"),
        synthesis_reliability=SynthesisReliability(overall_score=0.8),
        research_note="Test research note.",
        next_actions=["Continue verification"],
    )


class TestReportArchiveSave:
    """Tests for ReportArchiveService.save_report."""

    def test_save_creates_report_file(self, tmp_path, monkeypatch):
        """Saving a report should create a JSON file in the archive directory."""
        monkeypatch.setenv("REPORT_ARCHIVE_DIR", str(tmp_path))
        from app.config import get_settings
        get_settings.cache_clear()

        service = ReportArchiveService()
        report = _build_report()
        summary = service.save_report(report)

        assert summary.topic == "test archive"
        assert summary.verdict == "overall_pass"
        assert summary.paper_count == 0
        assert summary.stage_count == 0

        # Verify file was created
        report_files = list(tmp_path.glob("report-*.json"))
        assert len(report_files) == 1

        get_settings.cache_clear()

    def test_save_creates_index_file(self, tmp_path, monkeypatch):
        """Saving a report should create or update the index.json file."""
        monkeypatch.setenv("REPORT_ARCHIVE_DIR", str(tmp_path))
        from app.config import get_settings
        get_settings.cache_clear()

        service = ReportArchiveService()
        report = _build_report()
        summary = service.save_report(report)

        index_path = tmp_path / "index.json"
        assert index_path.exists()
        index_data = json.loads(index_path.read_text(encoding="utf-8"))
        assert len(index_data) == 1
        assert index_data[0]["report_id"] == summary.report_id

        get_settings.cache_clear()

    def test_save_multiple_reports(self, tmp_path, monkeypatch):
        """Saving multiple reports should accumulate in the index."""
        monkeypatch.setenv("REPORT_ARCHIVE_DIR", str(tmp_path))
        from app.config import get_settings
        get_settings.cache_clear()

        service = ReportArchiveService()
        summary1 = service.save_report(_build_report())
        summary2 = service.save_report(_build_report())

        history = service.list_reports()
        assert len(history) == 2
        assert history[0].report_id == summary2.report_id  # Most recent first

        get_settings.cache_clear()


class TestReportArchiveList:
    """Tests for ReportArchiveService.list_reports."""

    def test_list_returns_empty_when_no_reports(self, tmp_path, monkeypatch):
        """Listing reports with empty archive should return empty list."""
        monkeypatch.setenv("REPORT_ARCHIVE_DIR", str(tmp_path))
        from app.config import get_settings
        get_settings.cache_clear()

        service = ReportArchiveService()
        reports = service.list_reports()
        assert reports == []

        get_settings.cache_clear()

    def test_list_returns_saved_reports(self, tmp_path, monkeypatch):
        """Listing should return summaries of all saved reports."""
        monkeypatch.setenv("REPORT_ARCHIVE_DIR", str(tmp_path))
        from app.config import get_settings
        get_settings.cache_clear()

        service = ReportArchiveService()
        service.save_report(_build_report())
        service.save_report(_build_report())

        reports = service.list_reports()
        assert len(reports) == 2

        get_settings.cache_clear()


class TestReportArchiveGet:
    """Tests for ReportArchiveService.get_report."""

    def test_get_returns_full_report(self, tmp_path, monkeypatch):
        """Getting a saved report by ID should return the full ResearchReport."""
        monkeypatch.setenv("REPORT_ARCHIVE_DIR", str(tmp_path))
        from app.config import get_settings
        get_settings.cache_clear()

        service = ReportArchiveService()
        report = _build_report()
        summary = service.save_report(report)

        loaded = service.get_report(summary.report_id)
        assert loaded.request.topic == "test archive"
        assert loaded.review_report.verdict == "overall_pass"
        assert loaded.research_note == "Test research note."
        assert loaded.next_actions == ["Continue verification"]

        get_settings.cache_clear()

    def test_get_roundtrips_all_fields(self, tmp_path, monkeypatch):
        """All report fields should survive a save/load round-trip."""
        monkeypatch.setenv("REPORT_ARCHIVE_DIR", str(tmp_path))
        from app.config import get_settings
        get_settings.cache_clear()

        service = ReportArchiveService()
        report = _build_report()
        summary = service.save_report(report)
        loaded = service.get_report(summary.report_id)

        assert loaded.request == report.request
        assert loaded.clarification == report.clarification
        assert loaded.brief == report.brief
        assert loaded.plan == report.plan
        assert loaded.gap_report == report.gap_report
        assert loaded.comparison == report.comparison

        get_settings.cache_clear()

    def test_get_raises_for_unknown_report_id(self, tmp_path, monkeypatch):
        """Getting a non-existent report should raise ArchivedReportNotFoundError."""
        monkeypatch.setenv("REPORT_ARCHIVE_DIR", str(tmp_path))
        from app.config import get_settings
        get_settings.cache_clear()

        from app.api_error import ArchivedReportNotFoundError
        service = ReportArchiveService()

        with pytest.raises(ArchivedReportNotFoundError):
            service.get_report("nonexistent-id")

        get_settings.cache_clear()


class TestReportArchiveSummary:
    """Tests for report summary generation."""

    def test_summary_contains_correct_metadata(self, tmp_path, monkeypatch):
        """Summary should contain correct paper count, stage count, and score."""
        monkeypatch.setenv("REPORT_ARCHIVE_DIR", str(tmp_path))
        from app.config import get_settings
        get_settings.cache_clear()

        service = ReportArchiveService()
        report = _build_report()
        # Add a paper to test paper_count
        from app.models.research_models import Paper
        report.papers = [
            Paper(
                paper_id="p1", title="Paper 1", authors=["A"],
                summary="Summary.", source="arxiv",
            )
        ]
        summary = service.save_report(report)

        assert summary.paper_count == 1
        assert summary.support_score == 0.8
        assert summary.verdict == "overall_pass"

        get_settings.cache_clear()
