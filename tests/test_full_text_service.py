"""test_full_text_service.py Tests for FullTextService: PDF download, parsing, chunking, and error degradation."""

from __future__ import annotations

from unittest.mock import Mock

import pytest
import requests

from app.constant.paper_constant import FULL_TEXT_SOURCE_PDF
from app.models.research_models import FullTextChunk, FullTextDocument, Paper
from app.services.infrastructure.full_text_service import FullTextService


def _build_fake_pdf_response() -> Mock:
    """Build a mock HTTP response with PDF content bytes."""
    return Mock(content=b"%PDF-1.4", raise_for_status=lambda: None)


def _build_fake_full_text_document(paper_id: str) -> FullTextDocument:
    """Build a sample FullTextDocument for testing."""
    return FullTextDocument(
        paper_id=paper_id,
        source=FULL_TEXT_SOURCE_PDF,
        page_count=1,
        chunks=[
            FullTextChunk(
                text="Introduction. Retrieval-augmented repair improves patch correctness.",
                section="Introduction",
                page=1,
            ),
            FullTextChunk(
                text="Method. The model retrieves bug-fix pairs and conditions generation on evidence.",
                section="Method",
                page=1,
            ),
        ],
    )


class TestLoadDocument:
    """Tests for FullTextService.load_document."""

    def test_loads_document_from_pdf_response(self, monkeypatch):
        """load_document should download PDF and return a chunked FullTextDocument."""
        service = FullTextService()
        paper = Paper(
            paper_id="mock-001",
            title="Code Repair with RAG",
            authors=["Alice"],
            summary="This paper studies automatic program repair.",
            published="2024-05-01",
            pdf_url="https://example.com/mock-001.pdf",
            source="openalex",
        )

        monkeypatch.setattr(requests, "get", lambda *a, **kw: _build_fake_pdf_response())
        monkeypatch.setattr(
            FullTextService,
            "_parse_pdf_bytes",
            lambda self, paper_id, pdf_bytes: _build_fake_full_text_document(paper_id),
        )

        document = service.load_document(paper)
        assert document is not None
        assert document.paper_id == "mock-001"
        assert document.page_count >= 1
        assert document.chunks
        assert all(chunk.page > 0 for chunk in document.chunks)
        assert all(chunk.section for chunk in document.chunks)

    def test_returns_none_when_pdf_url_is_empty(self, monkeypatch):
        """load_document should return None when the paper has no PDF URL."""
        service = FullTextService()
        paper = Paper(
            paper_id="no-pdf",
            title="No PDF Paper",
            authors=["Alice"],
            summary="Summary.",
            source="arxiv",
        )

        document = service.load_document(paper)
        assert document is None

    def test_raises_download_error_on_network_failure(self, monkeypatch):
        """load_document should raise FullTextDownloadError when download fails."""
        from app.api_error import FullTextDownloadError

        service = FullTextService()
        paper = Paper(
            paper_id="fail-001",
            title="Fail Paper",
            authors=["Alice"],
            summary="Summary.",
            pdf_url="https://example.com/fail.pdf",
            source="arxiv",
        )

        monkeypatch.setattr(
            requests, "get",
            lambda *a, **kw: (_ for _ in ()).throw(requests.RequestException("network error")),
        )

        with pytest.raises(FullTextDownloadError):
            service.load_document(paper)


class TestLoadDocuments:
    """Tests for FullTextService.load_documents (batch mode)."""

    def test_loads_multiple_documents(self, monkeypatch):
        """load_documents should load documents for multiple papers."""
        service = FullTextService()
        papers = [
            Paper(
                paper_id="p1", title="Paper 1", authors=["A"],
                summary="Summary.", pdf_url="https://example.com/p1.pdf", source="openalex",
            ),
            Paper(
                paper_id="p2", title="Paper 2", authors=["B"],
                summary="Summary.", pdf_url="https://example.com/p2.pdf", source="arxiv",
            ),
        ]

        monkeypatch.setattr(requests, "get", lambda *a, **kw: _build_fake_pdf_response())
        monkeypatch.setattr(
            FullTextService,
            "_parse_pdf_bytes",
            lambda self, paper_id, pdf_bytes: FullTextDocument(
                paper_id=paper_id,
                source=FULL_TEXT_SOURCE_PDF,
                page_count=1,
                chunks=[FullTextChunk(text="Test chunk.", section="Intro", page=1)],
            ),
        )

        result = service.load_documents(papers, max_papers=2)
        assert len(result) == 2
        assert "p1" in result
        assert "p2" in result

    def test_degrades_gracefully_when_all_downloads_fail(self, monkeypatch):
        """load_documents should return empty dict when all downloads fail."""
        service = FullTextService()
        papers = [
            Paper(
                paper_id="p1", title="Paper 1", authors=["A"],
                summary="Summary.", pdf_url="https://example.com/p1.pdf", source="openalex",
            ),
        ]

        monkeypatch.setattr(
            requests, "get",
            lambda *a, **kw: (_ for _ in ()).throw(requests.RequestException("network error")),
        )

        result = service.load_documents(papers, max_papers=1)
        assert result == {}

    def test_respects_max_papers_limit(self, monkeypatch):
        """load_documents should only process up to max_papers."""
        service = FullTextService()
        papers = [
            Paper(
                paper_id=f"p{i}", title=f"Paper {i}", authors=["A"],
                summary="Summary.", pdf_url=f"https://example.com/p{i}.pdf", source="openalex",
            )
            for i in range(5)
        ]

        monkeypatch.setattr(requests, "get", lambda *a, **kw: _build_fake_pdf_response())
        monkeypatch.setattr(
            FullTextService,
            "_parse_pdf_bytes",
            lambda self, paper_id, pdf_bytes: FullTextDocument(
                paper_id=paper_id,
                source=FULL_TEXT_SOURCE_PDF,
                page_count=1,
                chunks=[FullTextChunk(text="Test.", section="Intro", page=1)],
            ),
        )

        result = service.load_documents(papers, max_papers=2)
        assert len(result) == 2


class TestTextNormalization:
    """Tests for FullTextService._normalize_text."""

    def test_collapses_whitespace(self):
        """Should collapse multiple whitespace into single spaces."""
        assert FullTextService._normalize_text("hello   world\n\nfoo") == "hello world foo"

    def test_strips_leading_trailing_whitespace(self):
        """Should strip leading and trailing whitespace."""
        assert FullTextService._normalize_text("  hello  ") == "hello"


class TestSectionInference:
    """Tests for FullTextService._infer_section_name."""

    def test_infers_section_from_heading(self):
        """Should infer section name from a capitalized heading."""
        assert FullTextService._infer_section_name("Introduction to the problem", 1) == "Introduction to the problem"

    def test_falls_back_to_page_number(self):
        """Should fall back to 'Page N' when no heading is found."""
        assert FullTextService._infer_section_name("some lower-case text here", 3) == "Page 3"
