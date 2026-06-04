"""memory_service 调研记忆服务。"""

from __future__ import annotations

import json
from typing import Optional

from app.api_error import MemoryLoadError, MemorySaveError
from app.config import get_settings
from app.models.research_models import ResearchMemory, ResearchPlan


class MemoryService:
    """MemoryService 本地调研记忆服务。"""

    def __init__(self) -> None:
        self.settings = get_settings()

    def load(self, topic: str) -> Optional[ResearchMemory]:
        """load 按主题读取历史记忆。"""
        memory_map = self._load_memory_map()
        memory_payload = memory_map.get(topic.lower())
        if not memory_payload:
            return None
        return ResearchMemory(**memory_payload)

    def save(
        self,
        topic: str,
        paper_ids: list[str],
        plan: ResearchPlan,
        latest_summary: str,
    ) -> ResearchMemory:
        """save 保存最新调研记忆。"""
        # 1. 读取已有记忆，避免覆盖其他主题。
        memory_map = self._load_memory_map()
        topic_key = topic.lower()
        previous_memory = memory_map.get(topic_key, {})

        # 2. 合并历史已读论文与偏好关键词。
        merged_paper_ids = list(
            dict.fromkeys(previous_memory.get("seen_paper_ids", []) + list(paper_ids))
        )
        merged_keywords = list(
            dict.fromkeys(previous_memory.get("preferred_keywords", []) + plan.search_keywords)
        )

        # 3. 写回本地文件，形成连续调研能力。
        memory = ResearchMemory(
            topic=topic,
            seen_paper_ids=merged_paper_ids,
            preferred_keywords=merged_keywords,
            latest_summary=latest_summary,
        )
        memory_map[topic_key] = memory.model_dump()
        self._write_memory_map(memory_map)
        return memory

    def _load_memory_map(self) -> dict:
        """_load_memory_map 读取记忆文件。"""
        memory_path = self.settings.get_memory_path()
        if not memory_path.exists():
            return {}
        try:
            return json.loads(memory_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise MemoryLoadError(f"读取记忆文件 {memory_path} 失败：{error}") from error

    def _write_memory_map(self, memory_map: dict) -> None:
        """_write_memory_map 写入记忆文件。"""
        memory_path = self.settings.get_memory_path()
        try:
            memory_path.parent.mkdir(parents=True, exist_ok=True)
            memory_path.write_text(
                json.dumps(memory_map, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except (OSError, TypeError, ValueError) as error:
            raise MemorySaveError(f"写入记忆文件 {memory_path} 失败：{error}") from error
