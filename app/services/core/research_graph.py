"""research_graph LangGraph 研究管线（5 节点图）。

图结构:
    plan → search → synthesize → review → finalize
                        ↺ should_refine=True (最多 1 次)
                          回到 search
"""

from __future__ import annotations

import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from langgraph.graph import END, START, StateGraph

from app.constant.prompt_constant import (
    COMPARE_AND_WRITE_PROMPT_TEMPLATE,
    PLAN_AND_SUPERVISE_PROMPT_TEMPLATE,
    SYSTEM_PROMPT_RESEARCH_ASSISTANT,
)
from app.models.research_models import (
    ComparisonSummary,
    EvidenceBundle,
    EvidenceSnippet,
    GapReport,
    PaperInsight,
    ResearchBrief,
    ResearchPlan,
    ResearchUnit,
    SSEEvent,
    StageTransition,
    SynthesisReliability,
)
from app.services.core.graph_state import GraphState
from app.services.core.llm_service import LLMService
from app.services.core.search_service import SearchService
from app.services.infrastructure.full_text_service import FullTextService
from app.services.infrastructure.memory_service import MemoryService
from app.services.pipeline.evidence_quality_service import EvidenceQualityService
from app.services.pipeline.extraction_service import ExtractionService
from app.services.pipeline.reviewer_service import ReviewerService

logger = logging.getLogger(__name__)


def _ensure_english_keywords(keywords: list[str], original_topic: str) -> list[str]:
    """确保搜索关键词包含英文词，否则用原始主题补充。"""
    has_english = any(re.search(r"[a-zA-Z]{3,}", kw) for kw in keywords)
    if has_english:
        return keywords
    logger.info("_ensure_english_keywords: all non-English, injecting topic: %s", original_topic)
    return [original_topic] + keywords


def _extract_insights_parallel(
    papers: list,
    full_text_documents: dict,
    extraction_service: ExtractionService,
) -> list[PaperInsight]:
    """并行提取多篇论文洞察。"""
    if not papers:
        return []
    if len(papers) <= 1:
        return [
            extraction_service.extract(paper, full_text_documents.get(paper.paper_id))
            for paper in papers
        ]
    results: dict[str, PaperInsight] = {}
    with ThreadPoolExecutor(max_workers=min(len(papers), 4)) as executor:
        futures = {
            executor.submit(
                extraction_service.extract, paper, full_text_documents.get(paper.paper_id),
            ): paper.paper_id
            for paper in papers
        }
        for future in as_completed(futures):
            paper_id = futures[future]
            try:
                results[paper_id] = future.result()
            except Exception as error:
                logger.warning("Extraction failed for paper_id=%s: %s", paper_id, error)
    return [results[paper.paper_id] for paper in papers if paper.paper_id in results]


def _build_evidence_bundle_tfidf(
    unit: ResearchUnit,
    insights: list[PaperInsight],
    full_text_docs: dict,
) -> EvidenceBundle:
    """Keyword matching to select relevant insights (no LLM)。"""
    query_text = f"{unit.question} {unit.focus}".lower()

    if not insights:
        return EvidenceBundle(
            unit_id=unit.unit_id, question=unit.question,
            synthesized_findings="", supporting_paper_ids=[], evidence=[], confidence=0.0,
        )

    # Extract both English keywords and Chinese character bigrams
    query_en_kw = set(re.findall(r"[a-zA-Z][a-zA-Z0-9\-]{2,}", query_text))
    query_cn_chars = set(re.findall(r"[一-鿿]", query_text))

    scored = []
    for insight in insights:
        content = f"{insight.problem} {insight.method} {insight.findings} {insight.paper.title} {insight.paper.summary}".lower()
        # English keyword overlap
        content_en_kw = set(re.findall(r"[a-zA-Z][a-zA-Z0-9\-]{2,}", content))
        en_overlap = len(query_en_kw & content_en_kw)
        # Chinese character overlap
        content_cn_chars = set(re.findall(r"[一-鿿]", content))
        cn_overlap = len(query_cn_chars & content_cn_chars)
        # Combined score: weight Chinese overlap more for Chinese topics
        score = en_overlap * 2 + cn_overlap
        scored.append((score, insight))

    scored.sort(key=lambda x: x[0], reverse=True)
    selected = [ins for score, ins in scored if score > 0][:3]
    if not selected:
        selected = [ins for _, ins in scored[:1]]

    paper_ids = [ins.paper.paper_id for ins in selected]
    evidence: list[EvidenceSnippet] = []
    for ins in selected:
        evidence.extend(ins.evidence[:3])

    findings = "；".join(ins.findings for ins in selected if ins.findings)
    confidence = min(0.3 + len(selected) * 0.2, 1.0)

    return EvidenceBundle(
        unit_id=unit.unit_id,
        question=unit.question,
        synthesized_findings=findings,
        supporting_paper_ids=paper_ids,
        evidence=evidence[:6],
        confidence=confidence,
    )


def _heuristic_gap_check(
    comparison: ComparisonSummary,
    evidence_bundles: list[EvidenceBundle],
) -> GapReport:
    """基于比较结果的空白启发式检测（无需 LLM）。"""
    gaps = comparison.gaps if comparison else []
    avg_conf = 0.0
    if evidence_bundles:
        avg_conf = sum(b.confidence for b in evidence_bundles) / len(evidence_bundles)

    need_follow_up = len(gaps) > 0 and avg_conf < 0.7
    return GapReport(
        need_follow_up=need_follow_up,
        missing_aspects=gaps[:3],
        follow_up_queries=gaps[:2] if need_follow_up else [],
        reasoning=f"比较分析发现 {len(gaps)} 个研究空白，证据置信度 {avg_conf:.2f}",
    )



# ── Node: plan ──────────────────────────────────────────────────────────────────


def plan_node(state: GraphState) -> dict:
    """plan_node 1 次 LLM 调用生成检索规划与研究单元。"""
    events: list[SSEEvent] = []
    stage_history: list[StageTransition] = []
    topic = state.get("topic", "")

    events.append(SSEEvent(
        event_type="stage_start", stage="plan",
        message="正在规划检索策略与研究单元...", progress=0.05,
    ))
    _t0 = time.monotonic()

    llm = LLMService()
    llm.ensure_enabled()

    ps_payload = llm.ask_json(
        system_prompt=SYSTEM_PROMPT_RESEARCH_ASSISTANT,
        user_prompt=PLAN_AND_SUPERVISE_PROMPT_TEMPLATE.format(
            topic=topic,
            research_goal=f"对「{topic}」进行全面学术调研",
            key_questions=["核心方法与代表性工作", "最新进展与趋势", "开放问题与挑战"],
        ),
        required_keys=["search_keywords", "research_units"],
    )

    raw_keywords = [str(k).strip() for k in ps_payload.get("search_keywords", []) if str(k).strip()]
    search_keywords = _ensure_english_keywords(raw_keywords, topic)[:4]

    raw_units = ps_payload.get("research_units", [])
    research_units = [
        ResearchUnit(
            unit_id=str(u.get("unit_id", f"unit-{i + 1}")),
            question=str(u.get("question", "")),
            focus=str(u.get("focus", "")),
            search_queries=_ensure_english_keywords(
                [str(q).strip() for q in u.get("search_queries", []) if str(q).strip()],
                topic,
            ),
            completion_definition=str(u.get("completion_definition", "")),
        )
        for i, u in enumerate(raw_units)
        if u.get("question")
    ]
    if not research_units:
        research_units = [
            ResearchUnit(
                unit_id="unit-1",
                question=f"调研「{topic}」的核心方法与最新进展",
                focus=topic,
                search_queries=[topic],
                completion_definition="形成可引用的结构化研究结论。",
            )
        ]

    plan = ResearchPlan(
        normalized_topic=str(ps_payload.get("normalized_topic", topic)).strip(),
        search_keywords=search_keywords,
        focus_areas=[str(f).strip() for f in ps_payload.get("focus_areas", []) if str(f).strip()],
        output_sections=[],
    )

    duration_ms = int((time.monotonic() - _t0) * 1000)
    stage_history.append(StageTransition(
        stage="plan", status="completed",
        summary=f"规划完成，{len(search_keywords)} 个检索词，{len(research_units)} 个研究单元",
        duration_ms=duration_ms,
    ))
    events.append(SSEEvent(
        event_type="stage_complete", stage="plan",
        message=f"检索规划完成（{len(search_keywords)} 个关键词，{len(research_units)} 个研究单元）",
        progress=0.2,
    ))

    return {
        "clarified_topic": topic,
        "search_keywords": search_keywords,
        "research_units": research_units,
        "plan": plan,
        "search_iteration": 0,
        "events": events,
        "stage_history": stage_history,
    }


# ── Node: search ────────────────────────────────────────────────────────────────


def search_node(state: GraphState) -> dict:
    """search_node 多源并行检索 + 全文加载 + 并行提取。"""
    events: list[SSEEvent] = []
    stage_history: list[StageTransition] = []

    max_papers = state.get("max_papers", 5)
    search_keywords = state.get("search_keywords", [])
    research_units = state.get("research_units", [])
    search_iteration = state.get("search_iteration", 0)
    follow_up_queries = state.get("follow_up_queries", [])

    stage_label = "follow_up" if search_iteration > 0 else "search"
    progress_base = 0.2 if search_iteration == 0 else 0.4

    events.append(SSEEvent(
        event_type="stage_start", stage=stage_label,
        message="正在多源并行检索论文...", progress=progress_base,
    ))
    _t0 = time.monotonic()

    search_service = SearchService()

    if search_iteration > 0 and follow_up_queries:
        queries = follow_up_queries
    else:
        queries = list(search_keywords)
        for unit in research_units:
            queries.extend(unit.search_queries)
        queries = list(dict.fromkeys(q for q in queries if q.strip()))[:4]

    papers = search_service.search_by_queries(queries=queries, max_papers=max_papers)

    if not papers:
        duration_ms = int((time.monotonic() - _t0) * 1000)
        stage_history.append(StageTransition(
            stage=stage_label, status="completed",
            summary="未检索到论文", duration_ms=duration_ms,
        ))
        events.append(SSEEvent(
            event_type="stage_complete", stage=stage_label,
            message="未检索到可用论文", progress=progress_base + 0.05,
        ))
        return {
            "papers": [],
            "insights": [],
            "full_text_documents": [],
            "events": events,
            "stage_history": stage_history,
        }

    events.append(SSEEvent(
        event_type="paper_found", stage=stage_label,
        message=f"已检索到 {len(papers)} 篇候选论文",
        progress=progress_base + 0.05,
        data={"paper_count": len(papers)},
    ))

    full_text_documents: dict = {}
    if state.get("enable_full_text", False):
        full_text_service = FullTextService()
        full_text_documents = full_text_service.load_documents(
            papers=papers,
            max_papers=state.get("max_full_text_papers", 0),
        )

    extraction_service = ExtractionService()
    insights = _extract_insights_parallel(papers, full_text_documents, extraction_service)

    duration_ms = int((time.monotonic() - _t0) * 1000)
    stage_history.append(StageTransition(
        stage=stage_label, status="completed",
        summary=f"检索完成，{len(papers)} 篇论文", duration_ms=duration_ms,
    ))
    events.append(SSEEvent(
        event_type="stage_complete", stage=stage_label,
        message=f"已完成论文检索与提取（{len(papers)} 篇论文，{len(insights)} 条洞察）",
        progress=progress_base + 0.15,
    ))

    return {
        "papers": papers,
        "full_text_documents": list(full_text_documents.values()),
        "insights": insights,
        "search_iteration": search_iteration + 1,
        "events": events,
        "stage_history": stage_history,
    }


# ── Node: synthesize ────────────────────────────────────────────────────────────


def synthesize_node(state: GraphState) -> dict:
    """synthesize_node 证据聚合 + 比较 + 空白检测 + 写作。"""
    events: list[SSEEvent] = []
    stage_history: list[StageTransition] = []

    topic = state.get("clarified_topic", state.get("topic", ""))
    insights = state.get("insights", [])
    papers = state.get("papers", [])
    research_units = state.get("research_units", [])
    search_iteration = state.get("search_iteration", 0)
    progress_base = 0.35 if search_iteration <= 1 else 0.55

    if not insights:
        return {
            "comparison": ComparisonSummary(overview="无可用论文数据"),
            "gap_report": GapReport(),
            "research_note": "",
            "next_actions": [],
            "evidence_bundles": [],
            "follow_up_queries": [],
            "events": events,
            "stage_history": stage_history,
        }

    brief = ResearchBrief(
        topic=topic, objective="",
        key_questions=[u.question for u in research_units],
    )

    # Evidence bundles (TF-IDF, no LLM)
    events.append(SSEEvent(
        event_type="stage_start", stage="evidence",
        message="正在聚合证据包...", progress=progress_base,
    ))
    _t0 = time.monotonic()
    full_text_docs = {doc.paper_id: doc for doc in state.get("full_text_documents", [])}
    evidence_bundles = [
        _build_evidence_bundle_tfidf(unit, insights, full_text_docs)
        for unit in research_units
    ]
    _dur = int((time.monotonic() - _t0) * 1000)
    stage_history.append(StageTransition(
        stage="evidence", status="completed",
        summary=f"已生成 {len(evidence_bundles)} 个证据包", duration_ms=_dur,
    ))
    events.append(SSEEvent(
        event_type="stage_complete", stage="evidence",
        message=f"已生成 {len(evidence_bundles)} 个证据包",
        progress=progress_base + 0.1,
    ))

    # Compare + Write (merged into 1 LLM call)
    events.append(SSEEvent(
        event_type="stage_start", stage="compare",
        message="正在执行比较分析与研究笔记生成...", progress=progress_base + 0.1,
    ))
    _t0 = time.monotonic()
    import json as _json
    paper_payload = _json.dumps([
        {
            "title": ins.paper.title,
            "problem": ins.problem,
            "method": ins.method,
            "innovation": ins.innovation,
            "findings": ins.findings,
            "limitation": ins.limitation,
        }
        for ins in insights
    ], ensure_ascii=False)
    llm = LLMService()
    merged_payload = llm.ask_json(
        system_prompt=SYSTEM_PROMPT_RESEARCH_ASSISTANT,
        user_prompt=COMPARE_AND_WRITE_PROMPT_TEMPLATE.format(
            topic=topic,
            paper_payload=paper_payload,
        ),
    )
    comparison = ComparisonSummary(
        overview=str(merged_payload.get("overview", "")).strip(),
        trends=[str(t).strip() for t in merged_payload.get("trends", []) if str(t).strip()],
        gaps=[str(g).strip() for g in merged_payload.get("gaps", []) if str(g).strip()],
        ideas=merged_payload.get("ideas", []),
    )
    research_note = str(merged_payload.get("research_note", "")).strip()
    next_actions = [str(a).strip() for a in merged_payload.get("next_actions", []) if str(a).strip()]
    _dur = int((time.monotonic() - _t0) * 1000)
    stage_history.append(StageTransition(
        stage="compare", status="completed",
        summary="比较分析与研究笔记完成", duration_ms=_dur,
    ))
    events.append(SSEEvent(
        event_type="stage_complete", stage="compare",
        message="已完成比较分析与研究笔记生成",
        progress=progress_base + 0.3,
    ))

    # Gap detect (heuristic, no LLM)
    _t0 = time.monotonic()
    gap_report = _heuristic_gap_check(comparison, evidence_bundles)

    follow_up_queries = gap_report.follow_up_queries if gap_report.need_follow_up else []

    return {
        "comparison": comparison,
        "gap_report": gap_report,
        "research_note": research_note,
        "next_actions": next_actions,
        "evidence_bundles": evidence_bundles,
        "follow_up_queries": follow_up_queries,
        "events": events,
        "stage_history": stage_history,
    }


# ── Node: review ────────────────────────────────────────────────────────────────


def review_node(state: GraphState) -> dict:
    """review_node 证据可靠性评估（1 LLM）+ 质量审查（1 LLM）。"""
    events: list[SSEEvent] = []
    stage_history: list[StageTransition] = []

    topic = state.get("clarified_topic", state.get("topic", ""))
    research_note = state.get("research_note", "")
    next_actions = state.get("next_actions", [])
    gap_report = state.get("gap_report")
    comparison = state.get("comparison")
    insights = state.get("insights", [])
    search_iteration = state.get("search_iteration", 0)
    progress_base = 0.75 if search_iteration <= 1 else 0.85

    # Evidence reliability assessment (1 LLM call)
    events.append(SSEEvent(
        event_type="stage_start", stage="reliability",
        message="正在评估证据可靠性...", progress=progress_base,
    ))
    _t0 = time.monotonic()
    quality_service = EvidenceQualityService()
    synthesis_reliability = quality_service.assess(
        topic=topic,
        insights=insights,
        comparison=comparison or ComparisonSummary(overview=""),
    )
    _dur = int((time.monotonic() - _t0) * 1000)
    stage_history.append(StageTransition(
        stage="reliability", status="completed",
        summary=f"可靠性评估完成，{len(synthesis_reliability.claims)} 个结论，总体 {synthesis_reliability.overall_score:.2f}",
        duration_ms=_dur,
    ))
    events.append(SSEEvent(
        event_type="stage_complete", stage="reliability",
        message=f"证据可靠性评估完成（{synthesis_reliability.strong_count} 强 / {synthesis_reliability.moderate_count} 中 / {synthesis_reliability.weak_count} 弱）",
        progress=progress_base + 0.08,
    ))

    # Build a lightweight citation verification for reviewer compatibility
    from app.models.research_models import CitationVerificationReport
    supported_count = synthesis_reliability.strong_count + synthesis_reliability.moderate_count
    unsupported_count = synthesis_reliability.weak_count + synthesis_reliability.isolated_count
    total = max(len(synthesis_reliability.claims), 1)
    citation_verification = CitationVerificationReport(
        overall_score=round(supported_count / total, 2),
        supported_count=supported_count,
        unsupported_count=unsupported_count,
    )

    # Review (1 LLM call)
    events.append(SSEEvent(
        event_type="stage_start", stage="review",
        message="正在执行质量审查...", progress=progress_base + 0.08,
    ))
    _t0 = time.monotonic()
    reviewer_service = ReviewerService()
    review_report = reviewer_service.review(
        topic=topic,
        research_note=research_note,
        gap_report=gap_report,
        next_actions=next_actions,
        citation_verification=citation_verification,
    )
    _dur = int((time.monotonic() - _t0) * 1000)
    stage_history.append(StageTransition(
        stage="review", status="completed",
        summary=f"verdict={review_report.verdict}", duration_ms=_dur,
    ))
    events.append(SSEEvent(
        event_type="stage_complete", stage="review",
        message=f"质量审查完成（{review_report.verdict}）",
        progress=progress_base + 0.15,
    ))

    return {
        "synthesis_reliability": synthesis_reliability,
        "review_report": review_report,
        "events": events,
        "stage_history": stage_history,
    }


# ── Node: finalize ──────────────────────────────────────────────────────────────


def finalize_node(state: GraphState) -> dict:
    """finalize_node 记忆保存（无 LLM 调用）。"""
    events: list[SSEEvent] = []
    stage_history: list[StageTransition] = []

    _t0 = time.monotonic()

    if state.get("include_memory", True):
        try:
            memory_service = MemoryService()
            memory_service.save(
                topic=state.get("topic", ""),
                paper_ids=[p.paper_id for p in state.get("papers", [])],
                plan=state.get("plan"),
                latest_summary=state.get("research_note", ""),
            )
        except Exception as error:
            logger.warning("Memory save failed: %s", error)

    duration_ms = int((time.monotonic() - _t0) * 1000)
    stage_history.append(StageTransition(
        stage="finalize", status="completed",
        summary="研究流程结束", duration_ms=duration_ms,
    ))

    return {
        "events": events,
        "stage_history": stage_history,
    }


# ── Conditional Edge ────────────────────────────────────────────────────────────


def should_refine(state: GraphState) -> str:
    """判断是否需要补充检索（最多 1 次循环）。"""
    gap_report = state.get("gap_report")
    search_iteration = state.get("search_iteration", 0)
    if gap_report and gap_report.need_follow_up and search_iteration < 1:
        logger.info(
            "should_refine=True, iteration=%s, queries=%s",
            search_iteration, state.get("follow_up_queries", []),
        )
        return "refine"
    return "continue"


# ── Graph Builder ───────────────────────────────────────────────────────────────


def build_research_graph():
    """编译并返回研究管线图。"""
    builder = StateGraph(GraphState)

    builder.add_node("plan", plan_node)
    builder.add_node("search", search_node)
    builder.add_node("synthesize", synthesize_node)
    builder.add_node("review", review_node)
    builder.add_node("finalize", finalize_node)

    builder.add_edge(START, "plan")
    builder.add_edge("plan", "search")
    builder.add_edge("search", "synthesize")
    builder.add_conditional_edges(
        "synthesize",
        should_refine,
        {"refine": "search", "continue": "review"},
    )
    builder.add_edge("review", "finalize")
    builder.add_edge("finalize", END)

    return builder.compile()
