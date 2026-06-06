"""debate_service Multi-Agent Debate 服务（Critic vs Writer）。"""

from __future__ import annotations

import json
import logging

from app.constant.prompt_constant import (
    CRITIC_PROMPT_TEMPLATE,
    DEBATE_REVISION_PROMPT_TEMPLATE,
    SYSTEM_PROMPT_RESEARCH_ASSISTANT,
)
from app.models.research_models import (
    ComparisonSummary,
    CriticWeakness,
    DebateRound,
    PaperInsight,
)
from app.services.core.llm_service import LLMService

logger = logging.getLogger(__name__)

DEFAULT_MAX_ROUNDS = 2
DEFAULT_QUALITY_THRESHOLD = 7
# Debate 跳过阈值：综合可靠性已较高且无显著 gap 时直接跳过，节省 token
DEBATE_SKIP_RELIABILITY_THRESHOLD = 0.75
DEBATE_SKIP_MIN_RESEARCH_NOTE_LEN = 80


class DebateService:
    """DebateService Critic-Writer 多轮辩论服务。"""

    def __init__(self) -> None:
        self.llm_service = LLMService()

    @staticmethod
    def should_skip(
        research_note: str,
        comparison: ComparisonSummary,
        synthesis_reliability_score: float = 0.0,
    ) -> bool:
        """should_skip 判断是否跳过 Debate（节流）。

        跳过条件（同时满足）：
        1. research_note 长度过短：跳过没意义，直接进入 review；
        2. 综合可靠性分数 ≥ 阈值，且 comparison.gaps 为空 —— 已无显著缺口；
        """
        # 1. 笔记过短：辩论价值不大
        if not research_note or len(research_note) < DEBATE_SKIP_MIN_RESEARCH_NOTE_LEN:
            return True
        # 2. 已经"足够好"且无 gap
        if (
            synthesis_reliability_score >= DEBATE_SKIP_RELIABILITY_THRESHOLD
            and not comparison.gaps
        ):
            return True
        return False

    def run_debate(
        self,
        topic: str,
        research_note: str,
        comparison: ComparisonSummary,
        insights: list[PaperInsight],
        next_actions: list[str],
        max_rounds: int = DEFAULT_MAX_ROUNDS,
        quality_threshold: int = DEFAULT_QUALITY_THRESHOLD,
    ) -> tuple[dict, list[DebateRound]]:
        """run_debate 执行 Critic-Writer 辩论循环。

        Returns:
            (revised_outputs, debate_log)
            revised_outputs 包含 research_note, comparison, next_actions
        """
        debate_log: list[DebateRound] = []
        current_note = research_note
        current_comparison = comparison
        current_next_actions = next_actions

        for round_num in range(1, max_rounds + 1):
            # Critic 评审
            critic_result = self._critic_review(
                topic, current_note, current_comparison, insights,
            )

            weaknesses = [
                CriticWeakness(
                    point=str(w.get("point", "")).strip(),
                    severity=str(w.get("severity", "medium")).strip(),
                    suggestion=str(w.get("suggestion", "")).strip(),
                )
                for w in critic_result.get("weaknesses", [])
                if str(w.get("point", "")).strip()
            ]
            quality_score = int(critic_result.get("overall_quality", 5))
            passed = bool(critic_result.get("pass", quality_score >= quality_threshold))

            round_entry = DebateRound(
                round_number=round_num,
                critic_weaknesses=weaknesses,
                critic_quality_score=quality_score,
                passed=passed,
            )

            logger.info(
                "Debate round %d: quality=%d, weaknesses=%d, passed=%s",
                round_num, quality_score, len(weaknesses), passed,
            )

            if passed:
                debate_log.append(round_entry)
                break

            # Writer 修订
            revision = self._writer_revise(
                topic, current_note, current_comparison, weaknesses, current_next_actions,
            )

            round_entry.revision_summary = str(revision.get("revision_summary", "")).strip()
            debate_log.append(round_entry)

            # 更新当前状态
            revised_note = str(revision.get("research_note", "")).strip()
            if revised_note:
                current_note = revised_note

            revised_overview = str(revision.get("overview", "")).strip()
            if revised_overview:
                current_comparison = ComparisonSummary(
                    overview=revised_overview,
                    trends=[str(t).strip() for t in revision.get("trends", current_comparison.trends) if str(t).strip()],
                    gaps=[str(g).strip() for g in revision.get("gaps", current_comparison.gaps) if str(g).strip()],
                    ideas=current_comparison.ideas,
                )

            revised_actions = [str(a).strip() for a in revision.get("next_actions", []) if str(a).strip()]
            if revised_actions:
                current_next_actions = revised_actions

        revised_outputs = {
            "research_note": current_note,
            "comparison": current_comparison,
            "next_actions": current_next_actions,
        }
        return revised_outputs, debate_log

    def _critic_review(
        self,
        topic: str,
        research_note: str,
        comparison: ComparisonSummary,
        insights: list[PaperInsight],
    ) -> dict:
        """_critic_review Critic Agent 审查研究综合。"""
        comparison_payload = json.dumps({
            "overview": comparison.overview,
            "trends": comparison.trends,
            "gaps": comparison.gaps,
        }, ensure_ascii=False)

        insights_payload = json.dumps([
            {
                "title": ins.paper.title,
                "method": ins.method,
                "findings": ins.findings,
                "confidence": ins.confidence,
            }
            for ins in insights[:10]
        ], ensure_ascii=False)

        return self.llm_service.ask_json(
            system_prompt=SYSTEM_PROMPT_RESEARCH_ASSISTANT,
            user_prompt=CRITIC_PROMPT_TEMPLATE.format(
                topic=topic,
                research_note=research_note,
                comparison_payload=comparison_payload,
                insights_payload=insights_payload,
            ),
            required_keys=["weaknesses", "overall_quality", "pass"],
        )

    def _writer_revise(
        self,
        topic: str,
        research_note: str,
        comparison: ComparisonSummary,
        weaknesses: list[CriticWeakness],
        next_actions: list[str],
    ) -> dict:
        """_writer_revise Writer Agent 根据 Critic 意见修订。"""
        comparison_payload = json.dumps({
            "overview": comparison.overview,
            "trends": comparison.trends,
            "gaps": comparison.gaps,
        }, ensure_ascii=False)

        critic_feedback = json.dumps([
            {"point": w.point, "severity": w.severity, "suggestion": w.suggestion}
            for w in weaknesses
        ], ensure_ascii=False)

        return self.llm_service.ask_json(
            system_prompt=SYSTEM_PROMPT_RESEARCH_ASSISTANT,
            user_prompt=DEBATE_REVISION_PROMPT_TEMPLATE.format(
                topic=topic,
                research_note=research_note,
                comparison_payload=comparison_payload,
                critic_feedback=critic_feedback,
            ),
            required_keys=["research_note", "revision_summary"],
        )
