"""main FastAPI 应用入口。"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from app.api_error import APIError
from app.config import get_settings
from app.logging_config import setup_logging
from app.models.research_models import (
    ReportArchiveSummary,
    ResearchReport,
    ResearchRequest,
    TrendAnalysisResult,
    PaperRecommendation,
)
from app.services.analysis.recommendation_service import RecommendationService
from app.services.infrastructure.report_archive_service import ReportArchiveService
from app.services.core.report_service import ReportService
from app.services.analysis.trend_analysis_service import TrendAnalysisService
from app.middleware.rate_limit import RateLimitMiddleware

setup_logging()

settings = get_settings()
report_service = ReportService()
report_archive_service = ReportArchiveService()
trend_analysis_service = TrendAnalysisService()
recommendation_service = RecommendationService()

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
app.add_middleware(RateLimitMiddleware, max_requests=3, window_seconds=60)

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
    """stream_research_report SSE 流式生成科研报告，实时推送阶段进度。"""
    logger.info(
        "SSE request received, topic=%s, max_papers=%s",
        request.get_topic(), request.get_max_papers(),
    )

    def event_generator():
        try:
            for event in report_service.generate_report_stream(request):
                event_data = event.model_dump()
                if event.event_type == "final_report" and event.data:
                    # 归档
                    try:
                        report = ResearchReport(**event.data)
                        _try_archive(report)
                    except Exception:
                        pass
                yield f"data: {json.dumps(event_data, ensure_ascii=False, default=str)}\n\n"
        except APIError as error:
            error_event = {
                "event_type": "error",
                "stage": "",
                "message": error.title,
                "progress": 0,
                "data": error.to_dict(),
            }
            yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"
        except Exception as error:
            error_event = {
                "event_type": "error",
                "stage": "",
                "message": "服务内部错误",
                "progress": 0,
                "data": {"detail": str(error)},
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


# ============ 内部工具 ============

def _try_archive(report: ResearchReport) -> None:
    """_try_archive 自动归档报告。"""
    try:
        summary = report_archive_service.save_report(report)
        logger.info("Report archived, report_id=%s, topic=%s", summary.report_id, summary.topic)
    except APIError as error:
        logger.info("Report archive skipped, error_code=%s, detail=%s", error.error_code, error.detail)
