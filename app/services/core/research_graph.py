"""research_graph LangGraph 研究管线（7 节点图）。

图结构:
    plan → search → synthesize → debate → review → fact_check → finalize
                        ↺ should_refine=True (最多 1 次)
                          回到 search
"""

from __future__ import annotations

import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from langgraph.graph import END, START, StateGraph

from app.constant.llm_constant import (
    GRAPH_EVENT_NODE_COMPLETE,
    GRAPH_EVENT_NODE_SKIP,
    GRAPH_EVENT_NODE_START,
)
from app.constant.prompt_constant import (
    PLAN_AND_SUPERVISE_PROMPT_TEMPLATE,
    SYSTEM_PROMPT_RESEARCH_ASSISTANT,
)
from app.constant.synthesis_constant import (
    ADAPTIVE_LOOP_SCORE_THRESHOLD,
    ADAPTIVE_WEIGHT_BUNDLE_CONFIDENCE,
    ADAPTIVE_WEIGHT_PAPER_COVERAGE,
    ADAPTIVE_WEIGHT_UNIT_CONFIDENCE,
    FOLLOW_UP_QUERY_LIMIT,
    MAX_REFINE_ROUNDS,
)
from app.models.research_models import (
    ComparisonSummary,
    EvidenceBundle,
    EvidenceSnippet,
    PaperInsight,
    ResearchPlan,
    ResearchUnit,
    SSEEvent,
    StageTransition,
    SynthesisReliability,
    UnitSynthesis,
)
from app.services.core.graph_state import GraphState
from app.services.core.llm_service import LLMService
from app.services.core.search_service import SearchService
from app.services.infrastructure.full_text_service import FullTextService
from app.services.infrastructure.memory_service import MemoryService
from app.services.infrastructure.structured_logging import (
    emit_event,
    get_current_stats,
)
from app.services.pipeline.evidence_quality_service import EvidenceQualityService
from app.services.pipeline.extraction_service import ExtractionService
from app.services.pipeline.fact_check_service import FactCheckService
from app.services.pipeline.contradiction_service import ContradictionService
from app.services.pipeline.reviewer_service import ReviewerService
from app.services.pipeline.unit_synthesis_service import UnitSynthesisService

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
    progress_callback=None,
) -> list[PaperInsight]:
    """并行提取多篇论文洞察。

    progress_callback: Optional[Callable[[int, int, str], None]]
        每完成一篇论文回调一次 (done, total, paper_title)，用于实时推送 SSE 进度。
    """
    if not papers:
        return []
    total = len(papers)
    if total <= 1:
        results_seq: list[PaperInsight] = []
        for idx, paper in enumerate(papers):
            results_seq.append(extraction_service.extract(paper, full_text_documents.get(paper.paper_id)))
            if progress_callback is not None:
                try:
                    progress_callback(idx + 1, total, paper.title or paper.paper_id)
                except Exception:  # 回调异常不应阻断主流程
                    pass
        return results_seq
    results: dict[str, PaperInsight] = {}
    with ThreadPoolExecutor(max_workers=min(len(papers), 4)) as executor:
        futures = {
            executor.submit(
                extraction_service.extract, paper, full_text_documents.get(paper.paper_id),
            ): paper
            for paper in papers
        }
        done_count = 0
        for future in as_completed(futures):
            paper = futures[future]
            try:
                results[paper.paper_id] = future.result()
            except Exception as error:
                logger.warning("Extraction failed for paper_id=%s: %s", paper.paper_id, error)
            done_count += 1
            if progress_callback is not None:
                try:
                    progress_callback(done_count, total, paper.title or paper.paper_id)
                except Exception:
                    pass
    return [results[paper.paper_id] for paper in papers if paper.paper_id in results]


def _merge_table_results_into_insights(
    insights: list[PaperInsight],
    full_text_documents: dict,
) -> None:
    """_merge_table_results_into_insights 把 PDF 表格抽取得到的定量结果回填到 insight。"""
    # 1. 没有 insight 或没有全文文档时直接返回，避免无谓循环
    if not insights or not full_text_documents:
        return
    # 2. 按 paper_id 找到对应文档，按三元组去重后追加
    for insight in insights:
        document = full_text_documents.get(insight.paper.paper_id)
        if document is None or not getattr(document, "tables", None):
            continue
        existing_keys = {
            (item.dataset, item.metric, item.value)
            for item in insight.quantitative_results
        }
        for table_item in document.tables:
            key = (table_item.dataset, table_item.metric, table_item.value)
            if key in existing_keys:
                continue
            insight.quantitative_results.append(table_item)
            existing_keys.add(key)


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


def _enrich_comparison_with_gaps(
    comparison: ComparisonSummary,
    evidence_bundles: list[EvidenceBundle],
    unit_syntheses: list[UnitSynthesis] | None = None,
    total_papers: int = 0,
) -> ComparisonSummary:
    """_enrich_comparison_with_gaps 综合多维信号判断是否需要回环检索。

    评分维度（加权和）：
    1. 证据包置信度均值（bundle.confidence）
    2. 单元综合置信度均值（unit_synthesis.confidence）
    3. 论文覆盖率（supporting_paper_ids 去重 / total_papers）

    若加权综合分 < ADAPTIVE_LOOP_SCORE_THRESHOLD 且 gaps 非空，则触发回环。
    """
    gaps = comparison.gaps if comparison else []
    # 1. 证据包平均置信度
    bundle_conf = 0.0
    if evidence_bundles:
        bundle_conf = sum(b.confidence for b in evidence_bundles) / len(evidence_bundles)
    # 2. 单元综合平均置信度
    unit_conf = 0.0
    if unit_syntheses:
        unit_conf = sum(u.confidence for u in unit_syntheses) / len(unit_syntheses)
    # 3. 论文覆盖率：去重后被任一 unit 引用的 paper / 总论文数
    coverage = 0.0
    if total_papers > 0 and unit_syntheses:
        cited: set[str] = set()
        for unit in unit_syntheses:
            cited.update(unit.supporting_paper_ids)
        coverage = min(len(cited) / total_papers, 1.0)
    # 4. 加权综合分
    composite_score = (
        ADAPTIVE_WEIGHT_BUNDLE_CONFIDENCE * bundle_conf
        + ADAPTIVE_WEIGHT_UNIT_CONFIDENCE * unit_conf
        + ADAPTIVE_WEIGHT_PAPER_COVERAGE * coverage
    )

    need_follow_up = (
        len(gaps) > 0 and composite_score < ADAPTIVE_LOOP_SCORE_THRESHOLD
    )
    comparison.need_follow_up = need_follow_up
    comparison.follow_up_queries = (
        gaps[:FOLLOW_UP_QUERY_LIMIT] if need_follow_up else []
    )
    comparison.gap_reasoning = (
        f"研究空白 {len(gaps)} 个；证据置信度 {bundle_conf:.2f}，"
        f"单元综合 {unit_conf:.2f}，论文覆盖 {coverage:.2f}，"
        f"综合分 {composite_score:.2f}（阈值 {ADAPTIVE_LOOP_SCORE_THRESHOLD:.2f}）"
    )
    return comparison


def _emit_node_start(node: str, **fields) -> None:
    """_emit_node_start 输出图节点开始的结构化日志。"""
    emit_event(logger, GRAPH_EVENT_NODE_START, node=node, **fields)


def _emit_node_complete(node: str, duration_ms: int, **fields) -> None:
    """_emit_node_complete 输出图节点完成的结构化日志（带耗时与 LLM 统计快照）。"""
    stats = get_current_stats()
    if stats is not None:
        fields.setdefault("llm_call_count", stats.call_count)
        fields.setdefault("llm_total_tokens", stats.total_tokens())
    emit_event(
        logger, GRAPH_EVENT_NODE_COMPLETE,
        node=node, duration_ms=duration_ms, **fields,
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
    _emit_node_start("plan", topic=topic[:80])
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

    # Self-Query 检索改写：把主题扩展为更多视角的子查询，与原关键词合并去重
    try:
        from app.services.pipeline.self_query_service import SelfQueryService
        sub_queries = SelfQueryService(llm_service=llm).expand_queries(topic, search_keywords)
        if sub_queries:
            merged_seen = {kw.lower() for kw in search_keywords}
            for q in sub_queries:
                if q.lower() not in merged_seen:
                    search_keywords.append(q)
                    merged_seen.add(q.lower())
            # 限制总查询数避免检索成本爆炸
            search_keywords = search_keywords[:8]
    except Exception as exc:  # pragma: no cover - 兜底，self-query 不阻断主流程
        logger.info("plan_node self-query expansion failed: %s", exc)

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
    _emit_node_complete(
        "plan", duration_ms,
        keyword_count=len(search_keywords),
        unit_count=len(research_units),
    )
    events.append(SSEEvent(
        event_type="stage_complete", stage="plan",
        message=f"检索规划完成（{len(search_keywords)} 个关键词，{len(research_units)} 个研究单元）",
        progress=0.2,
        data={"duration_ms": duration_ms},
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
    topic = state.get("clarified_topic", state.get("topic", ""))

    stage_label = "follow_up" if search_iteration > 0 else "search"
    progress_base = 0.2 if search_iteration == 0 else 0.4

    events.append(SSEEvent(
        event_type="stage_start", stage=stage_label,
        message="正在多源并行检索论文...", progress=progress_base,
    ))
    _emit_node_start(
        "search", iteration=search_iteration, query_count=len(search_keywords),
    )
    _t0 = time.monotonic()

    search_service = SearchService()

    if search_iteration > 0 and follow_up_queries:
        queries = follow_up_queries
    else:
        queries = list(search_keywords)
        for unit in research_units:
            queries.extend(unit.search_queries)
        queries = list(dict.fromkeys(q for q in queries if q.strip()))[:4]

    papers = search_service.search_by_queries(queries=queries, max_papers=max_papers, topic=topic)

    if not papers:
        duration_ms = int((time.monotonic() - _t0) * 1000)
        stage_history.append(StageTransition(
            stage=stage_label, status="completed",
            summary="未检索到论文", duration_ms=duration_ms,
        ))
        events.append(SSEEvent(
            event_type="stage_complete", stage=stage_label,
            message="未检索到可用论文", progress=progress_base + 0.05,
            data={"duration_ms": duration_ms},
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

    # 1. 实时进度回调：每完成一篇论文抽取就推送 paper_extracted 事件，
    #    避免 LLM 长耗时阶段前端长时间无任何反馈
    from app.services.infrastructure.task_registry import emit_progress as _emit_progress
    progress_span = 0.10  # 抽取阶段占进度条 10% 的可见区段
    progress_anchor = progress_base + 0.05

    def _on_extract_done(done: int, total: int, title: str) -> None:
        ratio = done / max(total, 1)
        _emit_progress(SSEEvent(
            event_type="paper_extracted",
            stage=stage_label,
            message=f"已完成 {done}/{total} 篇论文洞察抽取",
            progress=min(progress_anchor + progress_span * ratio, progress_anchor + progress_span),
            data={"done": done, "total": total, "title": title[:120]},
        ))

    insights = _extract_insights_parallel(
        papers, full_text_documents, extraction_service, progress_callback=_on_extract_done,
    )

    # 合并 PDF 表格抽取得到的定量结果，按 (dataset, metric, value) 三元组去重
    _merge_table_results_into_insights(insights, full_text_documents)

    duration_ms = int((time.monotonic() - _t0) * 1000)
    stage_history.append(StageTransition(
        stage=stage_label, status="completed",
        summary=f"检索完成，{len(papers)} 篇论文", duration_ms=duration_ms,
    ))
    _emit_node_complete(
        "search", duration_ms,
        iteration=search_iteration,
        paper_count=len(papers), insight_count=len(insights),
    )
    events.append(SSEEvent(
        event_type="stage_complete", stage=stage_label,
        message=f"已完成论文检索与提取（{len(papers)} 篇论文，{len(insights)} 条洞察）",
        progress=progress_base + 0.15,
        data={"duration_ms": duration_ms},
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
    """synthesize_node 证据聚合 + 按 ResearchUnit 分别综合 + 全局聚合写作。"""
    events: list[SSEEvent] = []
    stage_history: list[StageTransition] = []

    topic = state.get("clarified_topic", state.get("topic", ""))
    insights = state.get("insights", [])
    research_units = state.get("research_units", [])
    search_iteration = state.get("search_iteration", 0)
    progress_base = 0.35 if search_iteration <= 1 else 0.55

    if not insights:
        return {
            "comparison": ComparisonSummary(overview="无可用论文数据"),
            "research_note": "",
            "next_actions": [],
            "evidence_bundles": [],
            "unit_syntheses": [],
            "follow_up_queries": [],
            "events": events,
            "stage_history": stage_history,
        }

    _emit_node_start("synthesize", iteration=search_iteration, unit_count=len(research_units))
    _node_t0 = time.monotonic()

    # 1. 证据包构建（TF-IDF，无 LLM）
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
        progress=progress_base + 0.08,
        data={"duration_ms": _dur},
    ))

    # 2. 按 ResearchUnit 并行综合，每个研究问题独立产出小节
    events.append(SSEEvent(
        event_type="stage_start", stage="unit_synthesis",
        message=f"正在按 {len(research_units)} 个研究问题分别综合...",
        progress=progress_base + 0.08,
    ))
    _t0 = time.monotonic()
    unit_synthesis_service = UnitSynthesisService()
    unit_syntheses: list[UnitSynthesis] = unit_synthesis_service.synthesize_units(
        topic=topic,
        units=research_units,
        evidence_bundles=evidence_bundles,
        insights=insights,
    )
    _dur = int((time.monotonic() - _t0) * 1000)
    stage_history.append(StageTransition(
        stage="unit_synthesis", status="completed",
        summary=f"已生成 {len(unit_syntheses)} 个研究单元小节", duration_ms=_dur,
    ))
    events.append(SSEEvent(
        event_type="stage_complete", stage="unit_synthesis",
        message=f"已完成 {len(unit_syntheses)} 个研究单元小节",
        progress=progress_base + 0.2,
        data={"duration_ms": _dur},
    ))

    # 3. 全局聚合：把多个 UnitSynthesis 合成 ComparisonSummary + research_note + next_actions
    events.append(SSEEvent(
        event_type="stage_start", stage="compare",
        message="正在执行全局聚合与研究笔记生成...",
        progress=progress_base + 0.2,
    ))
    _t0 = time.monotonic()
    comparison, research_note, next_actions = unit_synthesis_service.aggregate_global(
        topic=topic,
        unit_syntheses=unit_syntheses,
    )
    _dur = int((time.monotonic() - _t0) * 1000)
    stage_history.append(StageTransition(
        stage="compare", status="completed",
        summary="全局聚合与研究笔记完成", duration_ms=_dur,
    ))
    events.append(SSEEvent(
        event_type="stage_complete", stage="compare",
        message="已完成全局聚合与研究笔记生成",
        progress=progress_base + 0.3,
        data={"duration_ms": _dur},
    ))

    # 4. 启发式补充研究空白与回检建议（综合 bundle + unit + 论文覆盖率）
    comparison = _enrich_comparison_with_gaps(
        comparison,
        evidence_bundles,
        unit_syntheses=unit_syntheses,
        total_papers=len(state.get("papers", [])),
    )
    follow_up_queries = comparison.follow_up_queries if comparison.need_follow_up else []

    _emit_node_complete(
        "synthesize", int((time.monotonic() - _node_t0) * 1000),
        iteration=search_iteration,
        unit_synthesis_count=len(unit_syntheses),
        need_follow_up=comparison.need_follow_up,
        gap_count=len(comparison.gaps),
    )

    return {
        "comparison": comparison,
        "research_note": research_note,
        "next_actions": next_actions,
        "evidence_bundles": evidence_bundles,
        "unit_syntheses": unit_syntheses,
        "follow_up_queries": follow_up_queries,
        "events": events,
        "stage_history": stage_history,
    }


# ── Node: debate ─────────────────────────────────────────────────────────────────


def debate_node(state: GraphState) -> dict:
    """debate_node Critic-Writer 多轮辩论，修订研究笔记与比较结论。"""
    events: list[SSEEvent] = []
    stage_history: list[StageTransition] = []

    research_note = state.get("research_note", "")
    insights = state.get("insights", [])
    search_iteration = state.get("search_iteration", 0)
    progress_base = 0.65 if search_iteration <= 1 else 0.75

    if not insights or not research_note:
        return {
            "debate_log": [],
            "events": events,
            "stage_history": stage_history,
        }

    # 1. 全局开关：默认关闭辩论以节省 ~150s LLM 推理时间（reviewer + fact_check 仍提供质量护栏）
    emit_event(
        logger, GRAPH_EVENT_NODE_SKIP,
        node="debate", reason="disabled_for_speed",
    )
    stage_history.append(StageTransition(
        stage="debate", status="skipped",
        summary="已关闭辩论以节省 LLM 调用",
        duration_ms=0,
    ))
    events.append(SSEEvent(
        event_type="stage_complete", stage="debate",
        message="跳过辩论（已关闭以节省时间）",
        progress=progress_base + 0.1,
        data={"duration_ms": 0},
    ))
    return {
        "debate_log": [],
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
    comparison = state.get("comparison")
    insights = state.get("insights", [])
    search_iteration = state.get("search_iteration", 0)
    progress_base = 0.75 if search_iteration <= 1 else 0.85

    # Evidence reliability assessment (1 LLM call)
    events.append(SSEEvent(
        event_type="stage_start", stage="reliability",
        message="正在评估证据可靠性...", progress=progress_base,
    ))
    _emit_node_start("review", iteration=search_iteration)
    _node_t0 = time.monotonic()
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
        data={"duration_ms": _dur},
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
        comparison=comparison,
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
        data={"duration_ms": _dur},
    ))

    _emit_node_complete(
        "review", int((time.monotonic() - _node_t0) * 1000),
        verdict=review_report.verdict,
        reliability_score=synthesis_reliability.overall_score,
    )

    return {
        "synthesis_reliability": synthesis_reliability,
        "review_report": review_report,
        "events": events,
        "stage_history": stage_history,
    }


# ── Node: fact_check ────────────────────────────────────────────────────────────


def fact_check_node(state: GraphState) -> dict:
    """fact_check_node 把 research_note 中的论断与已抽证据反查匹配。"""
    events: list[SSEEvent] = []
    stage_history: list[StageTransition] = []

    research_note = state.get("research_note", "")
    insights = state.get("insights", [])
    evidence_bundles = state.get("evidence_bundles", [])
    search_iteration = state.get("search_iteration", 0)
    progress_base = 0.9 if search_iteration <= 1 else 0.95

    # 1. 没有 note 或没有证据时跳过，不再产出空报告事件，避免噪音
    if not research_note or not insights:
        return {
            "events": events,
            "stage_history": stage_history,
        }

    events.append(SSEEvent(
        event_type="stage_start", stage="fact_check",
        message="正在对研究笔记中的论断做事实校验...",
        progress=progress_base,
    ))
    _emit_node_start("fact_check", iteration=search_iteration)
    _t0 = time.monotonic()

    # 2. 调用 FactCheckService 做关键词级反查
    fact_check_service = FactCheckService()
    fact_check_report = fact_check_service.fact_check(
        research_note=research_note,
        insights=insights,
        evidence_bundles=evidence_bundles,
    )

    _dur = int((time.monotonic() - _t0) * 1000)
    stage_history.append(StageTransition(
        stage="fact_check", status="completed",
        summary=(
            f"论断校验完成，{fact_check_report.supported_count} 支撑 / "
            f"{fact_check_report.weak_count} 弱 / "
            f"{fact_check_report.unsupported_count} 无证据"
        ),
        duration_ms=_dur,
    ))
    events.append(SSEEvent(
        event_type="stage_complete", stage="fact_check",
        message=(
            f"论断校验完成（{fact_check_report.supported_count} 支撑 / "
            f"{fact_check_report.weak_count} 弱 / "
            f"{fact_check_report.unsupported_count} 无证据，整体 "
            f"{fact_check_report.overall_score:.2f}）"
        ),
        progress=progress_base + 0.05,
        data={"duration_ms": _dur},
    ))

    _emit_node_complete(
        "fact_check", _dur,
        total_claims=fact_check_report.total_claims,
        supported=fact_check_report.supported_count,
        unsupported=fact_check_report.unsupported_count,
        nli_verified=fact_check_report.nli_verified_count,
    )

    # 3. 跨论文矛盾识别（失败不阻断主流程）
    contradictions = []
    try:
        contradictions = ContradictionService().detect(insights)
    except Exception as exc:
        logger.info("fact_check_node contradiction detection failed: %s", exc)
    if contradictions:
        events.append(SSEEvent(
            event_type="progress", stage="fact_check",
            message=f"检测到 {len(contradictions)} 组跨论文矛盾",
            progress=progress_base + 0.05,
            data={"contradiction_count": len(contradictions)},
        ))

    return {
        "fact_check_report": fact_check_report,
        "contradictions": contradictions,
        "events": events,
        "stage_history": stage_history,
    }


# ── Node: finalize ──────────────────────────────────────────────────────────────


def finalize_node(state: GraphState) -> dict:
    """finalize_node 记忆保存（无 LLM 调用）。"""
    events: list[SSEEvent] = []
    stage_history: list[StageTransition] = []

    _emit_node_start("finalize")
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
    _emit_node_complete("finalize", duration_ms)
    events.append(SSEEvent(
        event_type="stage_complete", stage="finalize",
        message="研究流程结束",
        progress=1.0,
        data={"duration_ms": duration_ms},
    ))

    return {
        "events": events,
        "stage_history": stage_history,
    }


# ── Conditional Edge ────────────────────────────────────────────────────────────


def should_refine(state: GraphState) -> str:
    """should_refine 自适应回环判定。

    满足条件即回到 search 节点：
    1. comparison.need_follow_up 为 True（_enrich_comparison_with_gaps 综合多维信号给出）
    2. 当前已检索轮次 < MAX_REFINE_ROUNDS
    """
    # 1. 全局开关：跳过 follow_up 第二轮（节省约 250s 单次任务耗时）
    #    若需恢复"研究空白补检索"行为，移除以下两行即可。
    logger.info("should_refine=False（已禁用 follow_up 二轮检索）")
    return "continue"
    comparison = state.get("comparison")
    search_iteration = state.get("search_iteration", 0)
    if comparison and comparison.need_follow_up and search_iteration < MAX_REFINE_ROUNDS:
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
    builder.add_node("debate", debate_node)
    builder.add_node("review", review_node)
    builder.add_node("fact_check", fact_check_node)
    builder.add_node("finalize", finalize_node)

    builder.add_edge(START, "plan")
    builder.add_edge("plan", "search")
    builder.add_edge("search", "synthesize")
    builder.add_conditional_edges(
        "synthesize",
        should_refine,
        {"refine": "search", "continue": "debate"},
    )
    builder.add_edge("debate", "review")
    builder.add_edge("review", "fact_check")
    builder.add_edge("fact_check", "finalize")
    builder.add_edge("finalize", END)

    return builder.compile()
