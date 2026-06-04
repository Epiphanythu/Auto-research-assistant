"""search_cache 搜索结果内存缓存（TTL 自动过期）。"""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from typing import Dict, List, Optional, Tuple

from app.models.research_models import Paper

logger = logging.getLogger(__name__)

DEFAULT_CACHE_TTL_SECONDS = 1800  # 30 minutes
DEFAULT_CACHE_MAX_ENTRIES = 200


class SearchCache:
    """SearchCache 搜索结果内存缓存，按 query+source 维度存储。"""

    def __init__(
        self,
        ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
        max_entries: int = DEFAULT_CACHE_MAX_ENTRIES,
    ) -> None:
        self._ttl = ttl_seconds
        self._max_entries = max_entries
        self._store: Dict[str, Tuple[float, List[Paper]]] = {}
        self._lock = threading.Lock()

    def get(self, query: str, source: str) -> Optional[List[Paper]]:
        """get 查询缓存，命中且未过期则返回结果，否则返回 None。"""
        key = self._make_key(query, source)
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            expires_at, papers = entry
            if time.monotonic() > expires_at:
                del self._store[key]
                logger.debug("SearchCache expired, key=%s", key[:16])
                return None
            logger.debug(
                "SearchCache hit, query=%s, source=%s, papers=%d",
                query[:40], source, len(papers),
            )
            return papers

    def put(self, query: str, source: str, papers: List[Paper]) -> None:
        """put 写入缓存。"""
        key = self._make_key(query, source)
        with self._lock:
            if len(self._store) >= self._max_entries:
                self._evict_locked()
            self._store[key] = (time.monotonic() + self._ttl, papers)
            logger.debug(
                "SearchCache put, query=%s, source=%s, papers=%d",
                query[:40], source, len(papers),
            )

    def clear(self) -> None:
        """clear 清空所有缓存。"""
        with self._lock:
            self._store.clear()

    def size(self) -> int:
        """size 返回当前缓存条目数。"""
        with self._lock:
            return len(self._store)

    @staticmethod
    def _make_key(query: str, source: str) -> str:
        """_make_key 生成缓存键。"""
        raw = f"{source}:{query.strip().lower()}"
        return hashlib.md5(raw.encode()).hexdigest()

    def _evict_locked(self) -> None:
        """_evict_locked 淘汰最早过期的条目（需在锁内调用）。"""
        if not self._store:
            return
        oldest_key = min(self._store, key=lambda k: self._store[k][0])
        del self._store[oldest_key]


# 进程级单例缓存
_global_cache: Optional[SearchCache] = None
_cache_lock = threading.Lock()


def get_search_cache() -> SearchCache:
    """get_search_cache 获取全局搜索缓存单例。"""
    global _global_cache
    with _cache_lock:
        if _global_cache is None:
            _global_cache = SearchCache()
        return _global_cache
