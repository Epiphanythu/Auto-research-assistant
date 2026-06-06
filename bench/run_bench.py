"""run_bench 离线评测脚本。

用途：基于 bench/cases.json 中的小样本主题，
驱动 ReportService 端到端跑研究报告，
并就关键词覆盖率、事实校验得分、论文数三类指标输出 Markdown 表格。

执行方式：
    uv run python -m bench.run_bench
    uv run python -m bench.run_bench --cases bench/cases.json --max-papers 3
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from app.models.research_models import ResearchRequest
from app.services.core.report_service import ReportService

logger = logging.getLogger("bench")

DEFAULT_CASES_PATH = Path(__file__).parent / "cases.json"
DEFAULT_MAX_PAPERS = 3


def _parse_args() -> argparse.Namespace:
    """_parse_args 解析命令行参数。"""
    parser = argparse.ArgumentParser(description="自动科研助手离线评测脚本")
    parser.add_argument(
        "--cases",
        default=str(DEFAULT_CASES_PATH),
        help="评测用例 JSON 文件路径",
    )
    parser.add_argument(
        "--max-papers",
        type=int,
        default=DEFAULT_MAX_PAPERS,
        help="每个用例的最大论文数",
    )
    return parser.parse_args()


def _load_cases(path: Path) -> List[Dict[str, Any]]:
    """_load_cases 读取评测用例列表。"""
    with path.open("r", encoding="utf-8") as fp:
        return json.load(fp)


def _compute_keyword_coverage(text: str, keywords: List[str]) -> float:
    """_compute_keyword_coverage 计算关键词覆盖率（不区分大小写）。"""
    if not keywords:
        return 0.0
    lowered = (text or "").lower()
    hit_count = sum(1 for kw in keywords if kw and kw.lower() in lowered)
    return round(hit_count / len(keywords), 3)


def _run_case(case: Dict[str, Any], max_papers: int) -> Dict[str, Any]:
    """_run_case 单个用例执行：调用 ReportService 并计算指标。"""
    # 1. 构造请求并跑通整个流水线
    request = ResearchRequest(
        topic=case["topic"],
        max_papers=max_papers,
        include_memory=False,
        enable_full_text=False,
    )
    report_service = ReportService()
    report = report_service.generate_report(request)
    # 2. 拼接 overview + research_note 后做关键词覆盖率
    overview = report.comparison.overview if report.comparison else ""
    research_note = report.research_note or ""
    coverage = _compute_keyword_coverage(
        f"{overview}\n{research_note}",
        case.get("expected_keywords", []),
    )
    fact_check_score = (
        report.fact_check_report.overall_score if report.fact_check_report else 0.0
    )
    return {
        "id": case["id"],
        "topic": case["topic"],
        "keyword_coverage": coverage,
        "fact_check_overall_score": round(float(fact_check_score), 3),
        "paper_count": len(report.papers),
        "verdict": report.review_report.verdict,
    }


def _print_markdown_table(rows: List[Dict[str, Any]]) -> None:
    """_print_markdown_table 把评测结果打印为 Markdown 表格。"""
    print("| ID | Topic | Keyword Coverage | Fact Check Score | Papers | Verdict |")
    print("| --- | --- | --- | --- | --- | --- |")
    for row in rows:
        print(
            f"| {row.get('id', '')} | {row.get('topic', '')} | "
            f"{row.get('keyword_coverage', 0.0)} | "
            f"{row.get('fact_check_overall_score', 0.0)} | "
            f"{row.get('paper_count', 0)} | "
            f"{row.get('verdict', '')} |"
        )


def main() -> None:
    """main 评测主流程。"""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s")
    args = _parse_args()
    cases = _load_cases(Path(args.cases))
    rows: List[Dict[str, Any]] = []
    # 1. 逐个用例执行，单个失败不影响整体
    for case in cases:
        try:
            row = _run_case(case, args.max_papers)
        except Exception as error:  # pragma: no cover - 评测兜底
            logger.warning("bench case failed, id=%s, error=%s", case.get("id"), error)
            row = {
                "id": case.get("id", ""),
                "topic": case.get("topic", ""),
                "keyword_coverage": 0.0,
                "fact_check_overall_score": 0.0,
                "paper_count": 0,
                "verdict": f"error:{type(error).__name__}",
            }
        rows.append(row)
    # 2. 输出汇总表格
    print()
    _print_markdown_table(rows)


if __name__ == "__main__":
    main()
