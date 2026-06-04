"""test_keyword_fallback.py 搜索关键词英文保障测试。"""

from __future__ import annotations

import pytest

from app.services.core.report_service import ReportService


class TestEnsureEnglishKeywords:
    """Tests for _ensure_english_keywords fallback logic."""

    def test_passes_through_english_keywords(self):
        keywords = ["program repair", "LLM", "automated patch"]
        result = ReportService._ensure_english_keywords(keywords, "LLM program repair")
        assert result == keywords

    def test_injects_original_topic_when_all_chinese(self):
        keywords = ["大语言模型", "自动修复"]
        result = ReportService._ensure_english_keywords(keywords, "LLM program repair")
        assert result[0] == "LLM program repair"
        assert "大语言模型" in result

    def test_passes_mixed_keywords(self):
        keywords = ["LLM repair", "代码修复"]
        result = ReportService._ensure_english_keywords(keywords, "LLM program repair")
        assert result == keywords

    def test_handles_empty_keywords(self):
        result = ReportService._ensure_english_keywords([], "LLM program repair")
        assert result[0] == "LLM program repair"

    def test_handles_short_english_tokens(self):
        # Single-letter or two-letter tokens should not count as English keywords
        keywords = ["AI 修复", "代码补丁"]
        result = ReportService._ensure_english_keywords(keywords, "AI code repair")
        assert result[0] == "AI code repair"
