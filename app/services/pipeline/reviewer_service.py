"""reviewer_service 研究报告审查服务。"""

from __future__ import annotations

import json

from app.constant.prompt_constant import (
    REVIEW_PROMPT_TEMPLATE,
    SYSTEM_PROMPT_RESEARCH_ASSISTANT,
)
from app.models.research_models import CitationVerificationReport, GapReport, ReviewReport
from app.services.core.llm_service import LLMService


class ReviewerService:
    """ReviewerService 研究结果审查器。"""

    def __init__(self) -> None:
        self.llm_service = LLMService()

    def review(
        self,
        topic: str,
        research_note: str,
        gap_report: GapReport,
        next_actions: list[str],
        citation_verification: CitationVerificationReport,
    ) -> ReviewReport:
        """review 对最终研究结果进行质量审查。"""
        # 1. 将研究笔记、空白和行动建议交给 reviewer，做最终质量门控。
        payload = self.llm_service.ask_json(
            system_prompt=SYSTEM_PROMPT_RESEARCH_ASSISTANT,
            user_prompt=REVIEW_PROMPT_TEMPLATE.format(
                topic=topic,
                research_note=research_note,
                gaps=json.dumps(gap_report.missing_aspects, ensure_ascii=False),
                next_actions=json.dumps(next_actions, ensure_ascii=False),
                citation_verification=json.dumps(
                    citation_verification.model_dump(),
                    ensure_ascii=False,
                ),
            ),
        )

        # 2. 输出 verdict、风险和修订建议，为后续迭代预留钩子。
        return ReviewReport(
            verdict=str(payload.get("verdict", "revision_needed")).strip(),
            strengths=[
                str(item).strip()
                for item in payload.get("strengths", [])
                if str(item).strip()
            ],
            risks=[
                str(item).strip()
                for item in payload.get("risks", [])
                if str(item).strip()
            ],
            revision_advice=[
                str(item).strip()
                for item in payload.get("revision_advice", [])
                if str(item).strip()
            ],
        )
