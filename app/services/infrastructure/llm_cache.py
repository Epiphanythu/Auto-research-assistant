"""llm_cache LLM 调用磁盘缓存（开发期减少 token 消耗 + 让单测/调试可重放）。"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
from pathlib import Path
from typing import Any, Dict, Optional

from app.constant.llm_constant import (
    LLM_CACHE_FILE_SUFFIX,
    LLM_CACHE_KEY_FIELDS,
)

logger = logging.getLogger(__name__)


class LLMCache:
    """LLMCache 基于磁盘的 LLM 调用结果缓存。"""

    def __init__(self, cache_dir: Path) -> None:
        self._cache_dir = cache_dir
        self._lock = threading.Lock()

    def get_cache_dir(self) -> Path:
        """get_cache_dir 获取缓存目录。"""
        return self._cache_dir

    @staticmethod
    def build_key(
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
    ) -> str:
        """build_key 由参与字段拼接后做 sha256 哈希得到缓存键。"""
        # 使用 LLM_CACHE_KEY_FIELDS 显式声明参与字段，避免随便加参数破坏命中
        payload = json.dumps(
            {
                LLM_CACHE_KEY_FIELDS[0]: model,
                LLM_CACHE_KEY_FIELDS[1]: system_prompt,
                LLM_CACHE_KEY_FIELDS[2]: user_prompt,
                LLM_CACHE_KEY_FIELDS[3]: round(temperature, 4),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def load(self, key: str) -> Optional[Dict[str, Any]]:
        """load 命中则返回缓存的 JSON 对象，未命中返回 None。"""
        path = self._key_to_path(key)
        if not path.exists():
            return None
        try:
            with self._lock:
                with path.open("r", encoding="utf-8") as f:
                    return json.load(f)
        except (OSError, json.JSONDecodeError) as error:
            logger.warning("LLMCache.load failed key=%s, error=%s", key, error)
            return None

    def save(self, key: str, value: Dict[str, Any]) -> None:
        """save 写入缓存（原子替换）。"""
        path = self._key_to_path(key)
        try:
            with self._lock:
                path.parent.mkdir(parents=True, exist_ok=True)
                tmp_path = path.with_suffix(path.suffix + ".tmp")
                with tmp_path.open("w", encoding="utf-8") as f:
                    json.dump(value, f, ensure_ascii=False)
                tmp_path.replace(path)
        except OSError as error:
            logger.warning("LLMCache.save failed key=%s, error=%s", key, error)

    def _key_to_path(self, key: str) -> Path:
        """_key_to_path 把缓存键映射到磁盘路径，做两级目录避免单目录文件过多。"""
        # 用前两位做一级目录，便于后续清理
        return self._cache_dir / key[:2] / f"{key}{LLM_CACHE_FILE_SUFFIX}"
