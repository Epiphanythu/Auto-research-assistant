"""self_query_service Self-Query 检索查询改写服务。

基于 LLM 围绕研究主题生成 3~5 条不同视角的子查询，提升多源召回。
"""

from __future__ import annotations

import logging
from typing import List

from app.constant.prompt_constant import SELF_QUERY_PROMPT_TEMPLATE, SYSTEM_PROMPT_RESEARCH_ASSISTANT
from app.services.core.llm_service import LLMService

logger = logging.getLogger(__name__)

# 最多注入的子查询数（避免检索成本过高）
MAX_SUB_QUERIES = 5


class SelfQueryService:
    """SelfQueryService 通过 LLM 把主题展开为多视角检索查询。"""

    def __init__(self, llm_service: LLMService | None = None) -> None:
        self._llm_service = llm_service or LLMService()

    def expand_queries(self, topic: str, existing_keywords: List[str]) -> List[str]:
        """expand_queries 基于主题与已有关键词生成多视角子查询。"""
        if not topic.strip():
            return []
        # 1. 调用 LLM，要求输出固定 JSON schema
        try:
            payload = self._llm_service.ask_json(
                system_prompt=SYSTEM_PROMPT_RESEARCH_ASSISTANT,
                user_prompt=SELF_QUERY_PROMPT_TEMPLATE.format(
                    topic=topic,
                    existing_keywords=", ".join(existing_keywords) or "(none)",
                ),
                required_keys=["queries"],
            )
        except Exception as error:  # 不让 self-query 阻断主流程
            logger.info("SelfQueryService.expand_queries failed, fallback empty: %s", error)
            return []
        # 2. 清洗并去重，保持原顺序
        raw_list = payload.get("queries") or []
        seen = {kw.strip().lower() for kw in existing_keywords if kw.strip()}
        result: List[str] = []
        for item in raw_list:
            text = str(item or "").strip()
            if not text:
                continue
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            result.append(text)
            if len(result) >= MAX_SUB_QUERIES:
                break
        logger.info(
            "SelfQueryService.expand_queries done, topic=%s, sub_queries=%d",
            topic[:40], len(result),
        )
        return result
