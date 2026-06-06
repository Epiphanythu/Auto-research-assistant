"""contradiction_service 跨论文论断矛盾识别服务。

输入候选论断（按论文聚合的 problem / method / findings / limitation 等关键陈述），
通过 LLM 识别"在同一议题上方向相反"的论断对，并输出 Contradiction 列表。
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from app.constant.prompt_constant import (
    CONTRADICTION_PROMPT_TEMPLATE,
    SYSTEM_PROMPT_RESEARCH_ASSISTANT,
)
from app.models.research_models import Contradiction, PaperInsight
from app.services.core.llm_service import LLMService

logger = logging.getLogger(__name__)

# 单次送入 LLM 的最大候选论断数量（控制 token 成本）
MAX_CANDIDATE_CLAIMS = 20
# 单条论断送入 LLM 的字符截断长度
CLAIM_TEXT_LIMIT = 240
# 输出最多保留的矛盾对数量
MAX_CONTRADICTIONS = 8


class ContradictionService:
    """ContradictionService 通过 LLM 识别跨论文的矛盾论断对。"""

    def __init__(self, llm_service: Optional[LLMService] = None) -> None:
        self._llm_service = llm_service or LLMService()

    def detect(self, insights: List[PaperInsight]) -> List[Contradiction]:
        """detect 基于多篇论文的洞察提取矛盾对。"""
        # 1. 入参校验：少于 2 篇论文无法构成矛盾对
        if not insights or len(insights) < 2:
            return []

        # 2. 构造候选论断列表（每篇论文取最具代表性的两条字段）
        candidates = self._build_candidates(insights)
        if len(candidates) < 2:
            return []

        # 3. 渲染 LLM 输入并调用
        claims_payload = self._render_payload(candidates)
        try:
            response = self._llm_service.ask_json(
                system_prompt=SYSTEM_PROMPT_RESEARCH_ASSISTANT,
                user_prompt=CONTRADICTION_PROMPT_TEMPLATE.format(
                    claims_payload=claims_payload,
                ),
                required_keys=["contradictions"],
            )
        except Exception as error:  # 矛盾识别失败不应阻断主流程
            logger.info("ContradictionService.detect failed, fallback empty: %s", error)
            return []

        # 4. 解析 + 校验：claim_id 必须在候选集中，且不能自指
        return self._parse_response(response, candidates)

    def _build_candidates(self, insights: List[PaperInsight]) -> List[Dict[str, str]]:
        """_build_candidates 提取每篇论文最具代表性的论断，限制总量。"""
        candidates: List[Dict[str, str]] = []
        for insight in insights:
            paper = insight.paper
            paper_id = paper.paper_id or paper.title[:20]
            # 1. findings 是最容易产生冲突的字段
            findings = (insight.findings or "").strip()
            if findings:
                candidates.append({
                    "claim_id": f"{paper_id}#findings",
                    "paper_id": paper_id,
                    "claim": findings[:CLAIM_TEXT_LIMIT],
                })
            # 2. limitation 经常给出对其他工作的反向评价
            limitation = (insight.limitation or "").strip()
            if limitation:
                candidates.append({
                    "claim_id": f"{paper_id}#limitation",
                    "paper_id": paper_id,
                    "claim": limitation[:CLAIM_TEXT_LIMIT],
                })
            if len(candidates) >= MAX_CANDIDATE_CLAIMS:
                break
        return candidates[:MAX_CANDIDATE_CLAIMS]

    def _render_payload(self, candidates: List[Dict[str, str]]) -> str:
        """_render_payload 把候选论断序列化为 LLM 易解析的列表文本。"""
        lines: List[str] = []
        for item in candidates:
            lines.append(
                f"- claim_id={item['claim_id']} | paper_id={item['paper_id']} | claim=\"{item['claim']}\""
            )
        return "\n".join(lines)

    def _parse_response(
        self,
        response: Dict,
        candidates: List[Dict[str, str]],
    ) -> List[Contradiction]:
        """_parse_response 把 LLM 输出转成 Contradiction 列表，丢弃非法引用。"""
        # 1. 建立 claim_id → 候选记录的索引
        claim_index = {item["claim_id"]: item for item in candidates}
        result: List[Contradiction] = []
        for raw in response.get("contradictions") or []:
            if not isinstance(raw, dict):
                continue
            claim_a_id = str(raw.get("claim_a_id") or "").strip()
            claim_b_id = str(raw.get("claim_b_id") or "").strip()
            # 2. 必须在候选中且非自指
            if not claim_a_id or not claim_b_id or claim_a_id == claim_b_id:
                continue
            cand_a = claim_index.get(claim_a_id)
            cand_b = claim_index.get(claim_b_id)
            if not cand_a or not cand_b:
                continue
            # 3. 必须来自不同论文，避免同一篇论文自相矛盾的低价值噪音
            if cand_a["paper_id"] == cand_b["paper_id"]:
                continue
            result.append(Contradiction(
                topic=str(raw.get("topic") or "").strip()[:120],
                claim_a=cand_a["claim"],
                claim_b=cand_b["claim"],
                paper_id_a=cand_a["paper_id"],
                paper_id_b=cand_b["paper_id"],
                rationale=str(raw.get("rationale") or "").strip()[:200],
            ))
            if len(result) >= MAX_CONTRADICTIONS:
                break
        logger.info(
            "ContradictionService.detect done, candidates=%d, contradictions=%d",
            len(candidates), len(result),
        )
        return result
