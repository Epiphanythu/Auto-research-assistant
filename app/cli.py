"""cli 命令行入口。"""

from __future__ import annotations

import argparse
import json
import logging

from app.logging_config import setup_logging
from app.models.research_models import ResearchRequest
from app.services.core.report_service import ReportService

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """build_parser 构建命令行参数。"""
    parser = argparse.ArgumentParser(description="自动科研助手 CLI")
    parser.add_argument("--topic", required=True, help="研究主题")
    parser.add_argument("--max-papers", type=int, default=5, help="最多检索论文数")
    parser.add_argument(
        "--no-memory",
        action="store_true",
        help="禁用本地记忆写入",
    )
    parser.add_argument(
        "--enable-full-text",
        action="store_true",
        help="启用 PDF 全文解析与正文级证据构建",
    )
    parser.add_argument(
        "--max-full-text-papers",
        type=int,
        default=2,
        help="最多执行全文解析的论文数",
    )
    return parser


def main() -> None:
    """main 执行命令行调研。"""
    # 1. 初始化统一日志配置，并解析参数构造请求对象。
    setup_logging()
    parser = build_parser()
    args = parser.parse_args()
    request = ResearchRequest(
        topic=args.topic,
        max_papers=args.max_papers,
        include_memory=not args.no_memory,
        enable_full_text=args.enable_full_text,
        max_full_text_papers=args.max_full_text_papers,
    )
    logger.info(
        "CLI request parsed, topic=%s, max_papers=%s, enable_full_text=%s",
        request.get_topic(),
        request.get_max_papers(),
        request.is_full_text_enabled(),
    )

    # 2. 调用主流程并打印结构化结果。
    report_service = ReportService()
    report = report_service.generate_report(request)
    logger.info(
        "CLI request completed, papers=%s, evidence_bundles=%s, verdict=%s",
        len(report.papers),
        len(report.evidence_bundles),
        report.review_report.verdict,
    )
    print(json.dumps(report.model_dump(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
