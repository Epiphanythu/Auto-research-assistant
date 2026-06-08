"""main FastAPI 应用入口。"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse

from app.api_error import APIError
from app.config import get_settings
from app.logging_config import setup_logging
from app.models.research_models import (
    ReportArchiveSummary,
    ResearchReport,
    ResearchRequest,
    SSEEvent,
    TrendAnalysisResult,
    PaperRecommendation,
)
from app.constant.report_constant import (
    EXPORT_FORMAT_JSON,
    EXPORT_FORMAT_MARKDOWN,
    JSON_MEDIA_TYPE,
    MARKDOWN_MEDIA_TYPE,
    SUPPORTED_EXPORT_FORMATS,
)
from app.services.analysis.recommendation_service import RecommendationService
from app.services.analysis.author_graph_service import AuthorGraphService
from app.services.infrastructure.report_archive_service import ReportArchiveService
from app.services.infrastructure.report_export_service import ReportExportService
from app.services.infrastructure.task_registry import (
    ResearchTask,
    get_task_registry,
    set_current_task,
)
from app.services.core.report_service import ReportService
from app.services.analysis.trend_analysis_service import TrendAnalysisService
from app.middleware.rate_limit import RateLimitMiddleware

setup_logging()

settings = get_settings()
report_service = ReportService()
report_archive_service = ReportArchiveService()
report_export_service = ReportExportService()
trend_analysis_service = TrendAnalysisService()
recommendation_service = RecommendationService()
author_graph_service = AuthorGraphService()

app = FastAPI(title=settings.get_app_name(), version="2.0.0")

# CORS middleware for frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting for research endpoints
app.add_middleware(
    RateLimitMiddleware,
    max_requests=3,
    window_seconds=60,
    max_in_flight=settings.get_research_max_in_flight(),
)

logger = logging.getLogger(__name__)


@app.exception_handler(APIError)
def handle_api_error(request: Request, error: APIError) -> JSONResponse:
    """handle_api_error 处理业务层结构化异常。"""
    logger.info(
        "APIError captured, path=%s, status_code=%s, error_code=%s, detail=%s",
        request.url.path, error.status_code, error.error_code, error.detail,
    )
    return JSONResponse(status_code=error.status_code, content=error.to_dict())


@app.exception_handler(RequestValidationError)
def handle_validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
    """handle_validation_error 处理请求参数校验失败。"""
    logger.info("RequestValidationError captured, path=%s, error=%s", request.url.path, error)
    return JSONResponse(
        status_code=422,
        content={
            "error_code": "request_validation_failed",
            "title": "请求参数校验失败",
            "detail": "提交的研究任务参数不符合接口要求。",
            "suggestion": "请检查主题、论文数量和全文解析参数的取值范围后重新提交。",
        },
    )


@app.exception_handler(Exception)
def handle_unexpected_error(request: Request, error: Exception) -> JSONResponse:
    """handle_unexpected_error 处理未预期异常。"""
    logger.exception("Unexpected error captured, path=%s, error=%s", request.url.path, error)
    return JSONResponse(
        status_code=500,
        content={
            "error_code": "internal_server_error",
            "title": "服务内部错误",
            "detail": "研究流程执行过程中发生未预期错误。",
            "suggestion": "请查看后端日志定位问题，并确认模型服务与外部依赖运行正常。",
        },
    )


@app.get("/health")
def health_check() -> dict:
    """health_check 健康检查接口（含诊断信息）。"""
    from app.services.infrastructure.search_cache import get_search_cache
    cache = get_search_cache()
    return {
        "status": "ok",
        "app": settings.get_app_name(),
        "version": "2.0.0",
        "llm_enabled": settings.is_llm_enabled(),
        "llm_model": settings.get_llm_model() if settings.is_llm_enabled() else "not_configured",
        "search_cache_size": cache.size(),
    }


@app.post("/api/v1/research", response_model=ResearchReport)
def generate_research_report(request: ResearchRequest) -> ResearchReport:
    """generate_research_report 生成自动科研报告（同步）。"""
    logger.info(
        "HTTP request received, topic=%s, max_papers=%s, enable_full_text=%s",
        request.get_topic(), request.get_max_papers(), request.is_full_text_enabled(),
    )
    report = report_service.generate_report(request)
    _try_archive(report)
    return report


@app.post("/api/v1/research/stream")
def stream_research_report(request: ResearchRequest) -> StreamingResponse:
    """stream_research_report 创建研究任务并 SSE 推送进度（首端连接）。"""
    logger.info(
        "SSE request received, topic=%s, max_papers=%s",
        request.get_topic(), request.get_max_papers(),
    )
    # 1. 在注册表中创建任务，并启动后台执行线程
    task = get_task_registry().create_task(request)
    _start_research_worker(task)
    return _build_task_stream_response(task, cursor=0, include_task_meta=True)


@app.get("/api/v1/research/tasks/{task_id}/stream")
def resume_research_stream(task_id: str, cursor: int = Query(default=0, ge=0)) -> StreamingResponse:
    """resume_research_stream 续连已有研究任务的 SSE 流，从游标继续推送。"""
    registry = get_task_registry()
    task = registry.get_task(task_id)
    if task is None:
        raise APIError(
            status_code=404,
            error_code="task_not_found",
            title="任务不存在或已过期",
            detail=f"未找到 task_id={task_id}",
            suggestion="请重新发起研究任务。",
        )
    return _build_task_stream_response(task, cursor=cursor, include_task_meta=False)


@app.get("/api/v1/research/tasks/{task_id}")
def get_research_task(task_id: str) -> dict:
    """get_research_task 查询任务当前状态摘要（不订阅事件）。"""
    task = get_task_registry().get_task(task_id)
    if task is None:
        raise APIError(
            status_code=404,
            error_code="task_not_found",
            title="任务不存在或已过期",
            detail=f"未找到 task_id={task_id}",
            suggestion="请重新发起研究任务。",
        )
    return {
        "task_id": task.task_id,
        "topic": task.topic,
        "status": task.get_status(),
        "event_count": len(task.events),
        "error_message": task.error_message,
    }


@app.delete("/api/v1/research/tasks/{task_id}")
def cancel_research_task(task_id: str) -> dict:
    """cancel_research_task 请求取消正在运行的研究任务。"""
    task = get_task_registry().get_task(task_id)
    if task is None:
        raise APIError(
            status_code=404,
            error_code="task_not_found",
            title="任务不存在或已过期",
            detail=f"未找到 task_id={task_id}",
            suggestion="任务可能已结束并被清理。",
        )
    if task.is_finished():
        return {"task_id": task_id, "status": task.get_status(), "cancelled": False}
    task.request_cancel()
    return {"task_id": task_id, "status": task.get_status(), "cancelled": True}


@app.post("/api/v1/research/replay")
def replay_research_report(payload: dict) -> StreamingResponse:
    """replay_research_report 基于归档报告以 SSE 形式回放合成事件。"""
    # 1. 校验入参，必须包含 report_id
    report_id = str(payload.get("report_id", "")).strip()
    if not report_id:
        raise APIError(
            status_code=400,
            error_code="replay_report_id_missing",
            title="缺少回放报告编号",
            detail="请求体必须包含 report_id。",
            suggestion="请在 POST body 中提供需要回放的 report_id。",
        )
    # 2. 直接通过 ReportService 的 replay 通道生成合成事件流
    archived = report_archive_service.get_report(report_id)
    request = archived.request

    def event_generator():
        for event in report_service.generate_report_stream(request, replay_report_id=report_id):
            event_data = event.model_dump()
            yield f"data: {json.dumps(event_data, ensure_ascii=False, default=str)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _build_task_stream_response(
    task: ResearchTask,
    cursor: int,
    include_task_meta: bool,
) -> StreamingResponse:
    """_build_task_stream_response 将任务事件流封装为 SSE 响应。"""
    registry = get_task_registry()

    def event_generator():
        # 1. 首条 meta 事件，便于前端拿到 task_id 持久化以备刷新续连
        if include_task_meta:
            meta = {
                "event_type": "task_created",
                "stage": "",
                "message": "研究任务已创建",
                "progress": 0.0,
                "data": {"task_id": task.task_id, "topic": task.topic},
            }
            yield f"data: {json.dumps(meta, ensure_ascii=False)}\n\n"
        # 2. 持续推送注册表中的事件，直到任务结束
        for _, event in registry.stream_events(task.task_id, cursor=cursor, wait_seconds=15.0):
            event_data = event.model_dump()
            yield f"data: {json.dumps(event_data, ensure_ascii=False, default=str)}\n\n"
        # 3. 末尾若任务异常，补一条 error
        if task.get_status() == "error" and task.error_message:
            error_event = {
                "event_type": "error",
                "stage": "",
                "message": "研究流程执行失败",
                "progress": 0.0,
                "data": {"detail": task.error_message},
            }
            yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _start_research_worker(task: ResearchTask) -> None:
    """_start_research_worker 在后台线程驱动 graph，并把事件追加到任务注册表。"""

    def _worker() -> None:
        task.mark_status("running")
        set_current_task(task)
        try:
            for event in report_service.generate_report_stream(task.request):
                if task.is_cancel_requested():
                    cancel_event = SSEEvent(
                        event_type="error", stage="",
                        message="研究任务已取消", progress=0.0,
                        data={"detail": "用户主动取消"},
                    )
                    task.append_event(cancel_event)
                    task.mark_status("cancelled")
                    return
                task.append_event(event)
                if event.event_type == "final_report" and event.data:
                    try:
                        report = ResearchReport(**event.data)
                        _try_archive(report)
                    except Exception:
                        logger.warning("Report archive failed in stream worker, task_id=%s", task.task_id, exc_info=True)
            task.mark_status("done")
        except APIError as error:
            task.append_event(SSEEvent(
                event_type="error", stage="",
                message=error.title, progress=0.0,
                data=error.to_dict(),
            ))
            task.mark_status("error", error_message=error.detail)
        except Exception as error:  # pragma: no cover - 兜底
            logger.exception("research task crashed, task_id=%s", task.task_id)
            task.append_event(SSEEvent(
                event_type="error", stage="",
                message="服务内部错误", progress=0.0,
                data={"detail": str(error)},
            ))
            task.mark_status("error", error_message=str(error))
        finally:
            # 清理 thread-local 任务上下文，避免线程被复用时串到下一次任务
            set_current_task(None)

    threading.Thread(target=_worker, name=f"research-{task.task_id[:8]}", daemon=True).start()


@app.get("/api/v1/reports", response_model=list[ReportArchiveSummary])
def list_archived_reports(
    limit: int = Query(default=12, ge=1, le=50),
) -> list[ReportArchiveSummary]:
    """list_archived_reports 获取历史报告列表。"""
    return report_archive_service.list_reports(limit=limit)


@app.get("/api/v1/reports/{report_id}", response_model=ResearchReport)
def get_archived_report(report_id: str) -> ResearchReport:
    """get_archived_report 按编号获取历史报告。"""
    return report_archive_service.get_report(report_id)


@app.get("/api/v1/reports/{report_id}/export")
def export_archived_report(
    report_id: str,
    format: str = Query(default=EXPORT_FORMAT_MARKDOWN, description="导出格式：md / json"),
):
    """export_archived_report 按格式导出历史报告（Markdown / JSON）。"""
    # 1. 校验导出格式
    fmt = format.lower()
    if fmt not in SUPPORTED_EXPORT_FORMATS:
        raise APIError(
            status_code=400,
            error_code="export_format_unsupported",
            title="导出格式不支持",
            detail=f"暂不支持的导出格式：{format}",
            suggestion=f"请使用受支持的格式：{', '.join(SUPPORTED_EXPORT_FORMATS)}",
        )
    # 2. 读取归档报告
    report = report_archive_service.get_report(report_id)
    # 3. 渲染并以下载形式返回
    if fmt == EXPORT_FORMAT_MARKDOWN:
        content = report_export_service.render_markdown(report)
        media_type = MARKDOWN_MEDIA_TYPE
        filename = report_export_service.build_filename(report, EXPORT_FORMAT_MARKDOWN)
    else:
        content = report_export_service.render_json(report)
        media_type = JSON_MEDIA_TYPE
        filename = report_export_service.build_filename(report, EXPORT_FORMAT_JSON)
    return PlainTextResponse(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.delete("/api/v1/reports/{report_id}")
def delete_archived_report(report_id: str) -> dict:
    """delete_archived_report 删除指定历史报告。"""
    report_archive_service.delete_report(report_id)
    return {"status": "ok", "report_id": report_id}


@app.get("/api/v1/research/reports/{report_id}/explainability")
def get_report_explainability(report_id: str) -> dict:
    """get_report_explainability 返回报告的可解释性面板字段。"""
    # 1. 加载完整归档报告
    report = report_archive_service.get_report(report_id)
    # 2. 汇总事实校验三档计数
    fact_check_summary = {"total": 0, "supported": 0, "unsupported": 0}
    if report.fact_check_report is not None:
        fact_check_summary = {
            "total": report.fact_check_report.total_claims,
            "supported": report.fact_check_report.supported_count,
            "unsupported": report.fact_check_report.unsupported_count,
        }
    # 3. 组装响应字段
    return {
        "report_id": report_id,
        "topic": report.request.topic,
        "llm_call_stats": report.llm_call_stats or {},
        "stage_history": [stage.model_dump() for stage in report.stage_history],
        "fact_check_summary": fact_check_summary,
        "contradiction_count": len(report.contradictions or []),
    }


# ============ 趋势分析 API ============

@app.get("/api/v1/trends/{topic}", response_model=TrendAnalysisResult)
def analyze_trends(
    topic: str,
    years: int = Query(default=5, ge=1, le=10),
) -> TrendAnalysisResult:
    """analyze_trends 分析研究主题的趋势。"""
    logger.info("Trend analysis request, topic=%s, years=%s", topic, years)
    return trend_analysis_service.analyze_trends(topic, years=years)


# ============ 论文推荐 API ============

@app.get("/api/v1/recommendations/{paper_id}", response_model=list[PaperRecommendation])
def recommend_from_paper(
    paper_id: str,
    limit: int = Query(default=10, ge=1, le=50),
) -> list[PaperRecommendation]:
    """recommend_from_paper 基于单篇论文推荐相似论文。"""
    logger.info("Recommendation request, paper_id=%s, limit=%s", paper_id, limit)
    return recommendation_service.recommend_from_paper(paper_id, limit=limit)


@app.post("/api/v1/recommendations/topic", response_model=list[PaperRecommendation])
def recommend_for_topic(
    topic: str = Query(...),
    limit: int = Query(default=10, ge=1, le=50),
) -> list[PaperRecommendation]:
    """recommend_for_topic 基于研究主题推荐论文。"""
    logger.info("Topic recommendation request, topic=%s", topic)
    return recommendation_service.recommend_for_topic(topic, existing_papers=[], limit=limit)


# ============ 作者机构图谱 API ============

@app.get("/api/v1/research/author-graph")
def get_author_graph(topic: str = Query(..., description="研究主题")) -> dict:
    """get_author_graph 基于最新归档报告构建作者-机构图谱。"""
    # 1. 在归档列表中按主题精确匹配最近一份报告
    target_report_id = ""
    summaries = report_archive_service.list_reports(limit=50)
    for summary in summaries:
        if summary.topic.strip() == topic.strip():
            target_report_id = summary.report_id
            break
    if not target_report_id:
        raise APIError(
            status_code=404,
            error_code="archived_report_not_found",
            title="未找到指定主题的归档报告",
            detail=f"未找到主题为「{topic}」的已归档报告。",
            suggestion="请先针对该主题生成并归档研究报告，或检查主题拼写。",
        )
    # 2. 加载完整报告并构建图谱
    report = report_archive_service.get_report(target_report_id)
    return author_graph_service.build(report.papers)


# ============ 内部工具 ============

def _try_archive(report: ResearchReport) -> None:
    """_try_archive 自动归档报告。"""
    try:
        summary = report_archive_service.save_report(report)
        logger.info("Report archived, report_id=%s, topic=%s", summary.report_id, summary.topic)
    except APIError as error:
        logger.info("Report archive skipped, error_code=%s, detail=%s", error.error_code, error.detail)
