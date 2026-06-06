"""unit_synthesis_service 按研究单元（ResearchUnit）独立综合的服务（Phase 2）。"""

from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

from app.constant.prompt_constant import (
    GLOBAL_SYNTHESIS_PROMPT_TEMPLATE,
    SYSTEM_PROMPT_RESEARCH_ASSISTANT,
    UNIT_SYNTHESIS_PROMPT_TEMPLATE,
)
from app.models.research_models import (
    ComparisonSummary,
    EvidenceBundle,
    InnovationIdea,
    PaperInsight,
    ResearchUnit,
    UnitSynthesis,
)
from app.services.core.llm_service import LLMService

logger = logging.getLogger(__name__)

# 单个研究单元最多送入 LLM 的论文数量，控制 token 成本
DEFAULT_INSIGHTS_PER_UNIT = 5
# 并行综合 unit 时的最大 worker 数
DEFAULT_UNIT_PARALLEL = 3


class UnitSynthesisService:
    """UnitSynthesisService 按 ResearchUnit 切片做小节级综合，再聚合为整体笔记。"""

    def __init__(self) -> None:
        self.llm_service = LLMService()

    def synthesize_units(
        self,
        topic: str,
        units: List[ResearchUnit],
        evidence_bundles: List[EvidenceBundle],
        insights: List[PaperInsight],
    ) -> List[UnitSynthesis]:
        """synthesize_units 为每个研究单元独立调用 LLM 生成 UnitSynthesis。"""
        # 1. 把 paper_id -> insight 索引一次，后续按 unit 选取候选论文。
        if not units or not insights:
            return []
        insight_by_id = {ins.paper.paper_id: ins for ins in insights if ins.paper.paper_id}
        bundles_by_unit = {b.unit_id: b for b in evidence_bundles}

        # 2. 并行处理多个 unit，每个 unit 单独调用一次 LLM。
        results: dict[str, UnitSynthesis] = {}
        with ThreadPoolExecutor(
            max_workers=min(len(units), DEFAULT_UNIT_PARALLEL)
        ) as executor:
            futures = {
                executor.submit(
                    self._synthesize_single_unit,
                    topic,
                    unit,
                    bundles_by_unit.get(unit.unit_id),
                    insight_by_id,
                    insights,
                ): unit.unit_id
                for unit in units
            }
            for future in as_completed(futures):
                unit_id = futures[future]
                try:
                    results[unit_id] = future.result()
                except Exception as error:
                    logger.warning(
                        "UnitSynthesisService.synthesize_units failed unit_id=%s, error=%s",
                        unit_id, error,
                    )

        # 3. 按原始 units 顺序输出。
        return [results[unit.unit_id] for unit in units if unit.unit_id in results]

    def aggregate_global(
        self,
        topic: str,
        unit_syntheses: List[UnitSynthesis],
    ) -> tuple[ComparisonSummary, str, list[str]]:
        """aggregate_global 把多个 UnitSynthesis 聚合为全局 ComparisonSummary + research_note + next_actions。"""
        # 1. 没有任何 unit 时返回空综合。
        if not unit_syntheses:
            return ComparisonSummary(overview="未生成有效的研究单元小节"), "", []

        units_payload = json.dumps([
            {
                "unit_id": u.unit_id,
                "question": u.question,
                "summary": u.summary,
                "key_methods": u.key_methods,
                "consensus": u.consensus,
                "disagreements": u.disagreements,
                "open_questions": u.open_questions,
                "supporting_paper_ids": u.supporting_paper_ids,
                "confidence": u.confidence,
            }
            for u in unit_syntheses
        ], ensure_ascii=False)

        # 2. 调用 LLM 做全局聚合，要求严格基于已有小节。
        payload = self.llm_service.ask_json(
            system_prompt=SYSTEM_PROMPT_RESEARCH_ASSISTANT,
            user_prompt=GLOBAL_SYNTHESIS_PROMPT_TEMPLATE.format(
                topic=topic,
                units_payload=units_payload,
            ),
        )

        # 3. 字段解析与防御性兜底。
        comparison = ComparisonSummary(
            overview=str(payload.get("overview", "")).strip(),
            trends=[str(t).strip() for t in payload.get("trends", []) if str(t).strip()],
            gaps=[str(g).strip() for g in payload.get("gaps", []) if str(g).strip()],
            ideas=[
                InnovationIdea(
                    title=str(idea.get("title", "")).strip(),
                    rationale=str(idea.get("rationale", "")).strip(),
                    risk=str(idea.get("risk", "")).strip(),
                )
                for idea in payload.get("ideas", [])
                if isinstance(idea, dict) and idea.get("title")
            ],
        )
        research_note = str(payload.get("research_note", "")).strip()
        next_actions = [
            str(a).strip() for a in payload.get("next_actions", []) if str(a).strip()
        ]
        return comparison, research_note, next_actions

    def _synthesize_single_unit(
        self,
        topic: str,
        unit: ResearchUnit,
        bundle: EvidenceBundle | None,
        insight_by_id: dict[str, PaperInsight],
        all_insights: List[PaperInsight],
    ) -> UnitSynthesis:
        """_synthesize_single_unit 单个 unit 的 LLM 综合调用。"""
        # 1. 选候选论文：优先使用 evidence_bundle 中筛出的论文；不足时用全部 insights 兜底。
        candidate_insights: List[PaperInsight] = []
        if bundle and bundle.supporting_paper_ids:
            for paper_id in bundle.supporting_paper_ids:
                ins = insight_by_id.get(paper_id)
                if ins is not None:
                    candidate_insights.append(ins)
        if len(candidate_insights) < 2:
            for ins in all_insights:
                if ins not in candidate_insights:
                    candidate_insights.append(ins)
                if len(candidate_insights) >= DEFAULT_INSIGHTS_PER_UNIT:
                    break
        candidate_insights = candidate_insights[:DEFAULT_INSIGHTS_PER_UNIT]

        # 2. 构造 LLM 输入 payload，仅暴露关键字段，控制 token。
        insights_payload = json.dumps([
            {
                "paper_id": ins.paper.paper_id,
                "title": ins.paper.title,
                "year": ins.paper.published[:4] if ins.paper.published else "",
                "problem": ins.problem,
                "method": ins.method,
                "innovation": ins.innovation,
                "findings": ins.findings,
                "limitation": ins.limitation,
            }
            for ins in candidate_insights
        ], ensure_ascii=False)

        payload = self.llm_service.ask_json(
            system_prompt=SYSTEM_PROMPT_RESEARCH_ASSISTANT,
            user_prompt=UNIT_SYNTHESIS_PROMPT_TEMPLATE.format(
                topic=topic,
                question=unit.question,
                focus=unit.focus or unit.question,
                insights_payload=insights_payload,
            ),
        )

        # 3. 字段解析；supporting_paper_ids 仅保留在候选集合内的，避免 LLM 编 id。
        valid_paper_ids = {ins.paper.paper_id for ins in candidate_insights}
        supporting = [
            str(pid).strip()
            for pid in payload.get("supporting_paper_ids", [])
            if str(pid).strip() in valid_paper_ids
        ]
        try:
            confidence = float(payload.get("confidence", 0.5))
        except (TypeError, ValueError):
            confidence = 0.5
        confidence = max(0.0, min(1.0, confidence))

        return UnitSynthesis(
            unit_id=unit.unit_id,
            question=unit.question,
            summary=str(payload.get("summary", "")).strip(),
            key_methods=[
                str(m).strip() for m in payload.get("key_methods", []) if str(m).strip()
            ],
            consensus=[
                str(c).strip() for c in payload.get("consensus", []) if str(c).strip()
            ],
            disagreements=[
                str(d).strip() for d in payload.get("disagreements", []) if str(d).strip()
            ],
            supporting_paper_ids=supporting,
            open_questions=[
                str(q).strip() for q in payload.get("open_questions", []) if str(q).strip()
            ],
            confidence=confidence,
        )
