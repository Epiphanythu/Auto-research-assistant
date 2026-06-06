"""report_service LangGraph 驱动的科研报告生成服务。"""

from __future__ import annotations

import logging
import re
from typing import Generator, Optional

from app.api_error import APIError
from app.config import get_settings
from app.models.research_models import (
    ComparisonSummary,
    DebateRound,
    ResearchPlan,
    ResearchReport,
    ResearchRequest,
    ResearchUnit,
    ReviewReport,
    SSEEvent,
    SynthesisReliability,
)
from app.services.infrastructure.report_archive_service import ReportArchiveService
from app.services.infrastructure.structured_logging import (
    LLMCallStats,
    llm_stats_scope,
)

logger = logging.getLogger(__name__)


class ResearchWorkflowError(APIError):
    """ResearchWorkflowError 研究流程关键失败异常。"""

    def __init__(self, detail: str, suggestion: str) -> None:
        super().__init__(
            status_code=502,
            error_code="research_workflow_failed",
            title="研究流程未完成",
            detail=detail,
            suggestion=suggestion,
        )


class ReportService:
    """ReportService LangGraph 驱动的自动科研助手。"""

    def generate_report(self, request: ResearchRequest) -> ResearchReport:
        """generate_report 同步生成完整调研报告。"""
        report_data = None
        for event in self.generate_report_stream(request):
            if event.event_type == "final_report":
                report_data = event.data
        if report_data is None:
            raise ResearchWorkflowError(
                detail="研究流程未产出最终报告。",
                suggestion="请检查后端日志确认失败阶段。",
            )
        if isinstance(report_data, ResearchReport):
            return report_data
        return ResearchReport(**report_data)

    def generate_report_stream(
        self,
        request: ResearchRequest,
        replay_report_id: Optional[str] = None,
    ) -> Generator[SSEEvent, None, None]:
        """generate_report_stream LangGraph 驱动的流式报告生成。"""
        from app.services.core.llm_service import LLMService
        from app.services.core.research_graph import build_research_graph

        # 1. Replay 模式：直接基于归档报告回放合成事件，不再触发 LangGraph
        settings = get_settings()
        target_replay_id = replay_report_id or (
            settings.get_replay_report_id() if settings.is_replay_mode_enabled() else ""
        )
        if target_replay_id:
            yield from self._replay_archived_report(request, target_replay_id)
            return

        logger.info(
            "ReportService.generate_report_stream start, topic=%s, max_papers=%s",
            request.get_topic(), request.get_max_papers(),
        )
        LLMService().ensure_enabled()

        graph = build_research_graph()
        initial_state = {
            "topic": request.get_topic(),
            "max_papers": request.get_max_papers(),
            "enable_full_text": request.is_full_text_enabled(),
            "max_full_text_papers": request.get_max_full_text_papers(),
            "include_memory": request.include_memory,
        }

        accumulated: dict = {"stage_history": []}
        # 1. 进入 LLM 调用统计作用域，整个图运行期间所有 LLM 调用都会落到此 stats
        stats = LLMCallStats()

        try:
            with llm_stats_scope(stats):
                for update in graph.stream(initial_state, stream_mode="updates"):
                    node_name = list(update.keys())[0]
                    node_output = update[node_name]

                    for event in node_output.get("events", []):
                        yield event

                    for key, value in node_output.items():
                        if key == "events":
                            continue
                        if key == "stage_history":
                            accumulated.setdefault("stage_history", []).extend(value)
                        else:
                            accumulated[key] = value
        except Exception as error:
            logger.exception("LangGraph stream failed: %s", error)
            yield SSEEvent(
                event_type="error", stage="",
                message="研究流程执行失败", progress=0,
                data={"detail": str(error)},
            )
            return

        topic = accumulated.get("clarified_topic", request.get_topic())
        report = ResearchReport(
            request=request,
            plan=accumulated.get("plan", ResearchPlan(
                normalized_topic=topic, search_keywords=[], focus_areas=[], output_sections=[],
            )),
            research_units=accumulated.get("research_units", []),
            papers=accumulated.get("papers", []),
            full_text_documents=accumulated.get("full_text_documents", []),
            insights=accumulated.get("insights", []),
            evidence_bundles=accumulated.get("evidence_bundles", []),
            comparison=accumulated.get("comparison", ComparisonSummary(overview="")),
            review_report=accumulated.get("review_report", ReviewReport(verdict="revision_needed")),
            synthesis_reliability=accumulated.get("synthesis_reliability"),
            stage_history=accumulated.get("stage_history", []),
            research_note=accumulated.get("research_note", ""),
            next_actions=accumulated.get("next_actions", []),
            debate_log=accumulated.get("debate_log", []),
            unit_syntheses=accumulated.get("unit_syntheses", []),
            fact_check_report=accumulated.get("fact_check_report"),
            contradictions=accumulated.get("contradictions", []),
            llm_call_stats=stats.to_dict(),
        )

        yield SSEEvent(
            event_type="final_report", stage="finalize",
            message="研究完成！", progress=1.0,
            data=report.model_dump(),
        )

    def _replay_archived_report(
        self,
        request: ResearchRequest,
        report_id: str,
    ) -> Generator[SSEEvent, None, None]:
        """_replay_archived_report 基于归档报告生成合成 SSE 事件序列。"""
        # 1. 加载归档报告，失败时直接抛 APIError 给上层兜底
        archive_service = ReportArchiveService()
        report = archive_service.get_report(report_id)
        logger.info(
            "ReportService._replay_archived_report start, replay_id=%s, topic=%s",
            report_id, report.request.topic,
        )
        # 2. 按归档的 stage_history 逐阶段产出 stage_start + stage_complete
        stage_count = max(len(report.stage_history), 1)
        for index, stage in enumerate(report.stage_history):
            base_progress = (index / stage_count) * 0.95
            yield SSEEvent(
                event_type="stage_start",
                stage=stage.stage,
                message=f"[Replay] 进入阶段：{stage.stage}",
                progress=round(base_progress, 3),
            )
            yield SSEEvent(
                event_type="stage_complete",
                stage=stage.stage,
                message=f"[Replay] {stage.summary}",
                progress=round(base_progress + (1.0 / stage_count) * 0.95, 3),
                data={"duration_ms": stage.duration_ms, "status": stage.status},
            )
        # 3. 用归档报告本身覆盖 request，便于前端正确展示原始上下文
        replay_report_dict = report.model_dump()
        replay_report_dict["request"] = request.model_dump()
        yield SSEEvent(
            event_type="final_report",
            stage="finalize",
            message="[Replay] 研究报告回放完成",
            progress=1.0,
            data=replay_report_dict,
        )

    # ── Static helpers (kept for test compatibility) ──

    @staticmethod
    def _build_search_queries(plan: ResearchPlan, research_units: list[ResearchUnit]) -> list[str]:
        """_build_search_queries 聚合规划关键词与研究单元查询。"""
        queries = list(plan.search_keywords)
        for research_unit in research_units:
            queries.extend(research_unit.search_queries)
        unique = list(dict.fromkeys(query for query in queries if query.strip()))
        return unique[:4]

    @staticmethod
    def _ensure_research_units(
        research_units: list[ResearchUnit],
        topic: str,
    ) -> list[ResearchUnit]:
        """_ensure_research_units 确保至少存在一个研究单元。"""
        if research_units:
            return research_units
        return [
            ResearchUnit(
                unit_id="unit-1",
                question=f"调研「{topic}」的核心方法与最新进展",
                focus=topic,
                search_queries=[topic],
                completion_definition="形成可引用的结构化研究结论。",
            )
        ]

    @staticmethod
    def _merge_papers(existing_papers, new_papers, max_papers: int):
        """_merge_papers 合并两轮检索得到的论文列表。"""
        unique_papers = {}
        for paper in existing_papers + new_papers:
            unique_papers.setdefault(paper.paper_id, paper)
        return list(unique_papers.values())[:max_papers]

    @staticmethod
    def _ensure_english_keywords(keywords: list[str], original_topic: str) -> list[str]:
        """_ensure_english_keywords 确保搜索关键词包含英文词。"""
        has_english = any(re.search(r"[a-zA-Z]{3,}", kw) for kw in keywords)
        if has_english:
            return keywords
        return [original_topic] + keywords
