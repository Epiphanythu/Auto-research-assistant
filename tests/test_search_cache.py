"""test_search_cache.py 搜索结果缓存测试。"""

from __future__ import annotations

import time
import threading

import pytest

from app.models.research_models import Paper
from app.services.infrastructure.search_cache import SearchCache


def _make_paper(paper_id: str, title: str) -> Paper:
    return Paper(paper_id=paper_id, title=title, authors=[], summary="Test.", source="arxiv")


class TestSearchCacheGetPut:
    """Tests for basic get/put operations."""

    def test_cache_miss_returns_none(self):
        cache = SearchCache()
        assert cache.get("query", "source") is None

    def test_cache_hit_returns_papers(self):
        cache = SearchCache()
        papers = [_make_paper("p1", "Paper 1")]
        cache.put("query", "source", papers)
        result = cache.get("query", "source")
        assert result is not None
        assert len(result) == 1
        assert result[0].paper_id == "p1"

    def test_cache_key_is_case_insensitive(self):
        cache = SearchCache()
        papers = [_make_paper("p1", "Paper 1")]
        cache.put("Query Text", "source", papers)
        assert cache.get("query text", "source") is not None
        assert cache.get("QUERY TEXT", "source") is not None

    def test_cache_key_includes_source(self):
        cache = SearchCache()
        papers = [_make_paper("p1", "Paper 1")]
        cache.put("query", "SemanticScholar", papers)
        assert cache.get("query", "SemanticScholar") is not None
        assert cache.get("query", "arXiv") is None


class TestSearchCacheExpiry:
    """Tests for TTL-based expiry."""

    def test_expired_entry_returns_none(self):
        cache = SearchCache(ttl_seconds=0)
        papers = [_make_paper("p1", "Paper 1")]
        cache.put("query", "source", papers)
        time.sleep(0.01)
        assert cache.get("query", "source") is None

    def test_non_expired_entry_returns_value(self):
        cache = SearchCache(ttl_seconds=60)
        papers = [_make_paper("p1", "Paper 1")]
        cache.put("query", "source", papers)
        assert cache.get("query", "source") is not None


class TestSearchCacheEviction:
    """Tests for max entries eviction."""

    def test_evicts_when_full(self):
        cache = SearchCache(ttl_seconds=60, max_entries=3)
        for i in range(5):
            cache.put(f"query-{i}", "source", [_make_paper(f"p{i}", f"P{i}")])
        assert cache.size() <= 3

    def test_clear_empties_cache(self):
        cache = SearchCache()
        cache.put("query", "source", [_make_paper("p1", "P1")])
        assert cache.size() == 1
        cache.clear()
        assert cache.size() == 0


class TestSearchCacheConcurrency:
    """Tests for thread safety."""

    def test_concurrent_reads_writes(self):
        cache = SearchCache()
        errors = []

        def writer(idx):
            try:
                cache.put(f"q-{idx}", "source", [_make_paper(f"p-{idx}", f"P-{idx}")])
            except Exception as e:
                errors.append(e)

        def reader(idx):
            try:
                cache.get(f"q-{idx}", "source")
            except Exception as e:
                errors.append(e)

        threads = []
        for i in range(20):
            threads.append(threading.Thread(target=writer, args=(i,)))
            threads.append(threading.Thread(target=reader, args=(i,)))
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors
