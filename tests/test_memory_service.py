"""test_memory_service.py Tests for MemoryService: save, load, merge, and error handling."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.api_error import MemoryLoadError, MemorySaveError
from app.models.research_models import ResearchPlan
from app.services.infrastructure.memory_service import MemoryService


class TestMemoryLoad:
    """Tests for MemoryService.load."""

    def test_load_returns_none_for_unknown_topic(self, tmp_path, monkeypatch):
        """Loading a topic that has never been saved should return None."""
        monkeypatch.setenv("MEMORY_PATH", str(tmp_path / "memory.json"))
        from app.config import get_settings
        get_settings.cache_clear()

        service = MemoryService()
        result = service.load("unknown topic")
        assert result is None

        get_settings.cache_clear()

    def test_load_returns_saved_memory(self, tmp_path, monkeypatch):
        """Loading a previously saved topic should return the stored memory."""
        monkeypatch.setenv("MEMORY_PATH", str(tmp_path / "memory.json"))
        from app.config import get_settings
        get_settings.cache_clear()

        service = MemoryService()
        plan = ResearchPlan(
            normalized_topic="test topic",
            search_keywords=["test"],
            focus_areas=["method"],
            output_sections=["Overview"],
        )
        saved = service.save(
            topic="test topic",
            paper_ids=["paper-1"],
            plan=plan,
            latest_summary="summary text",
        )

        loaded = service.load("test topic")
        assert loaded is not None
        assert loaded.topic == "test topic"
        assert "paper-1" in loaded.seen_paper_ids
        assert loaded.latest_summary == "summary text"

        get_settings.cache_clear()

    def test_load_raises_structured_error_for_invalid_json(self, tmp_path, monkeypatch):
        """Loading a corrupted memory file should raise MemoryLoadError."""
        memory_path = tmp_path / "memory.json"
        memory_path.write_text("{invalid json", encoding="utf-8")
        monkeypatch.setenv("MEMORY_PATH", str(memory_path))
        from app.config import get_settings
        get_settings.cache_clear()

        service = MemoryService()
        with pytest.raises(MemoryLoadError) as exc_info:
            service.load("test topic")

        assert exc_info.value.error_code == "memory_load_failed"

        get_settings.cache_clear()

    def test_load_is_case_insensitive(self, tmp_path, monkeypatch):
        """Loading a topic should match regardless of case."""
        monkeypatch.setenv("MEMORY_PATH", str(tmp_path / "memory.json"))
        from app.config import get_settings
        get_settings.cache_clear()

        service = MemoryService()
        plan = ResearchPlan(
            normalized_topic="Test Topic",
            search_keywords=["test"],
            focus_areas=["method"],
            output_sections=["Overview"],
        )
        service.save(
            topic="Test Topic",
            paper_ids=["p1"],
            plan=plan,
            latest_summary="summary",
        )

        loaded = service.load("test topic")
        assert loaded is not None
        assert loaded.topic == "Test Topic"

        get_settings.cache_clear()


class TestMemorySave:
    """Tests for MemoryService.save."""

    def test_save_creates_memory_file(self, tmp_path, monkeypatch):
        """Saving memory should create the memory file on disk."""
        memory_path = tmp_path / "memory.json"
        monkeypatch.setenv("MEMORY_PATH", str(memory_path))
        from app.config import get_settings
        get_settings.cache_clear()

        service = MemoryService()
        plan = ResearchPlan(
            normalized_topic="test topic",
            search_keywords=["test"],
            focus_areas=["method"],
            output_sections=["Overview"],
        )
        saved = service.save(
            topic="test topic",
            paper_ids=["paper-1"],
            plan=plan,
            latest_summary="summary",
        )

        assert saved.topic == "test topic"
        assert saved.seen_paper_ids == ["paper-1"]
        assert memory_path.exists()

        get_settings.cache_clear()

    def test_save_merges_paper_ids_on_repeated_saves(self, tmp_path, monkeypatch):
        """Saving the same topic twice should merge paper IDs without duplicates."""
        monkeypatch.setenv("MEMORY_PATH", str(tmp_path / "memory.json"))
        from app.config import get_settings
        get_settings.cache_clear()

        service = MemoryService()
        plan = ResearchPlan(
            normalized_topic="test topic",
            search_keywords=["test"],
            focus_areas=["method"],
            output_sections=["Overview"],
        )
        service.save(topic="test topic", paper_ids=["p1", "p2"], plan=plan, latest_summary="first")
        saved = service.save(topic="test topic", paper_ids=["p2", "p3"], plan=plan, latest_summary="second")

        assert saved.seen_paper_ids == ["p1", "p2", "p3"]
        assert saved.latest_summary == "second"

        get_settings.cache_clear()

    def test_save_merges_keywords_on_repeated_saves(self, tmp_path, monkeypatch):
        """Saving the same topic twice should merge keywords without duplicates."""
        monkeypatch.setenv("MEMORY_PATH", str(tmp_path / "memory.json"))
        from app.config import get_settings
        get_settings.cache_clear()

        service = MemoryService()
        plan1 = ResearchPlan(
            normalized_topic="test topic",
            search_keywords=["keyword-1", "keyword-2"],
            focus_areas=["method"],
            output_sections=["Overview"],
        )
        plan2 = ResearchPlan(
            normalized_topic="test topic",
            search_keywords=["keyword-2", "keyword-3"],
            focus_areas=["method"],
            output_sections=["Overview"],
        )
        service.save(topic="test topic", paper_ids=["p1"], plan=plan1, latest_summary="first")
        saved = service.save(topic="test topic", paper_ids=["p1"], plan=plan2, latest_summary="second")

        assert saved.preferred_keywords == ["keyword-1", "keyword-2", "keyword-3"]

        get_settings.cache_clear()

    def test_save_preserves_other_topics(self, tmp_path, monkeypatch):
        """Saving one topic should not overwrite another topic's memory."""
        monkeypatch.setenv("MEMORY_PATH", str(tmp_path / "memory.json"))
        from app.config import get_settings
        get_settings.cache_clear()

        service = MemoryService()
        plan = ResearchPlan(
            normalized_topic="test topic",
            search_keywords=["test"],
            focus_areas=["method"],
            output_sections=["Overview"],
        )
        service.save(topic="topic A", paper_ids=["p1"], plan=plan, latest_summary="A")
        service.save(topic="topic B", paper_ids=["p2"], plan=plan, latest_summary="B")

        loaded_a = service.load("topic A")
        loaded_b = service.load("topic B")
        assert loaded_a is not None
        assert loaded_b is not None
        assert loaded_a.latest_summary == "A"
        assert loaded_b.latest_summary == "B"

        get_settings.cache_clear()

    def test_save_raises_structured_error_for_write_failure(self, tmp_path, monkeypatch):
        """Saving should raise MemorySaveError when disk write fails."""
        memory_path = tmp_path / "memory.json"
        monkeypatch.setenv("MEMORY_PATH", str(memory_path))
        from app.config import get_settings
        get_settings.cache_clear()

        def fake_write_text(*args, **kwargs):
            raise OSError("disk full")

        monkeypatch.setattr(Path, "write_text", fake_write_text)

        service = MemoryService()
        plan = ResearchPlan(
            normalized_topic="test topic",
            search_keywords=["test"],
            focus_areas=["method"],
            output_sections=["Overview"],
        )
        with pytest.raises(MemorySaveError) as exc_info:
            service.save(
                topic="test topic",
                paper_ids=["paper-1"],
                plan=plan,
                latest_summary="summary",
            )

        assert exc_info.value.error_code == "memory_save_failed"

        get_settings.cache_clear()
