"""report_archive_service 报告归档服务。"""

from __future__ import annotations

import json
import re
import threading
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from app.api_error import (
    ArchivedReportNotFoundError,
    InvalidReportIdError,
    ReportArchiveLoadError,
    ReportArchiveSaveError,
)
from app.config import get_settings
from app.constant.report_constant import (
    DEFAULT_REPORT_ARCHIVE_INDEX_FILE,
    DEFAULT_REPORT_HISTORY_LIMIT,
    REPORT_ID_PATTERN,
)
from app.models.research_models import ReportArchiveSummary, ResearchReport


class ReportArchiveService:
    """ReportArchiveService 研究报告归档与历史记录服务。"""

    def __init__(self) -> None:
        # 1. 索引更新需要和报告文件写入/删除保持同一临界区，避免并发请求互相覆盖 index.json。
        self.settings = get_settings()
        self._index_lock = threading.Lock()

    def save_report(self, report: ResearchReport) -> ReportArchiveSummary:
        """save_report 保存研究报告归档。"""
        # 1. 生成报告编号、摘要与目标路径。
        archive_dir = self.settings.get_report_archive_dir()
        report_id = self._build_report_id()
        created_at = datetime.now().isoformat(timespec="seconds")
        report_summary = self._build_summary(report_id, created_at, report)
        report_path = self._get_report_path(archive_dir, report_id)
        index_path = self._get_index_path(archive_dir)

        try:
            archive_dir.mkdir(parents=True, exist_ok=True)
        except (OSError, TypeError, ValueError) as error:
            raise ReportArchiveSaveError(f"准备归档目录 {archive_dir} 失败：{error}") from error

        # 2. 在同一临界区内完成报告写入和索引更新，避免并发写入丢索引。
        with self._index_lock:
            self._write_json_file(report_path, report.model_dump(), "报告文件")
            history_items = self._load_index(index_path)
            history_items = [item for item in history_items if item.report_id != report_id]
            history_items.insert(0, report_summary)
            self._write_index(index_path, history_items)
        return report_summary

    def list_reports(self, limit: int = DEFAULT_REPORT_HISTORY_LIMIT) -> list[ReportArchiveSummary]:
        """list_reports 读取历史报告摘要列表。"""
        archive_dir = self.settings.get_report_archive_dir()
        index_path = self._get_index_path(archive_dir)
        history_items = self._load_index(index_path)
        return history_items[:limit]

    def get_report(self, report_id: str) -> ResearchReport:
        """get_report 按编号读取完整历史报告。"""
        # 1. 先校验编号格式，避免异常路径片段影响归档目录边界。
        self._validate_report_id(report_id)
        archive_dir = self.settings.get_report_archive_dir()
        report_path = self._get_report_path(archive_dir, report_id)
        if not report_path.exists():
            raise ArchivedReportNotFoundError(report_id)

        try:
            report_payload = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise ReportArchiveLoadError(f"读取报告文件 {report_path} 失败：{error}") from error
        return ResearchReport(**report_payload)

    def delete_report(self, report_id: str) -> None:
        """delete_report 删除指定报告及其索引条目。"""
        # 1. 先校验编号格式，避免删除归档目录外的文件。
        self._validate_report_id(report_id)
        archive_dir = self.settings.get_report_archive_dir()
        report_path = self._get_report_path(archive_dir, report_id)
        index_path = self._get_index_path(archive_dir)

        if not report_path.exists():
            raise ArchivedReportNotFoundError(report_id)

        # 1. 删除报告文件并同步更新索引，避免并发删除/保存打乱历史列表。
        with self._index_lock:
            try:
                report_path.unlink()
            except OSError as error:
                raise ReportArchiveSaveError(f"删除报告文件 {report_path} 失败：{error}") from error

            history_items = self._load_index(index_path)
            history_items = [item for item in history_items if item.report_id != report_id]
            self._write_index(index_path, history_items)

    @staticmethod
    def _build_report_id() -> str:
        """_build_report_id 生成报告编号。"""
        return f"report-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:8]}"

    @staticmethod
    def _get_index_path(archive_dir: Path) -> Path:
        """_get_index_path 获取归档索引文件路径。"""
        return archive_dir / DEFAULT_REPORT_ARCHIVE_INDEX_FILE

    @staticmethod
    def _get_report_path(archive_dir: Path, report_id: str) -> Path:
        """_get_report_path 获取单份报告文件路径。"""
        return archive_dir / f"{report_id}.json"

    @staticmethod
    def _validate_report_id(report_id: str) -> None:
        """_validate_report_id 校验归档报告编号格式。"""
        if not re.fullmatch(REPORT_ID_PATTERN, report_id):
            raise InvalidReportIdError(report_id)

    @staticmethod
    def _build_summary(
        report_id: str,
        created_at: str,
        report: ResearchReport,
    ) -> ReportArchiveSummary:
        """_build_summary 从完整报告生成归档摘要。"""
        return ReportArchiveSummary(
            report_id=report_id,
            topic=report.request.topic,
            created_at=created_at,
            paper_count=len(report.papers),
            stage_count=len(report.stage_history),
            support_score=report.synthesis_reliability.overall_score if report.synthesis_reliability else 0.0,
            verdict=report.review_report.verdict,
        )

    def _load_index(self, index_path: Path) -> list[ReportArchiveSummary]:
        """_load_index 读取归档索引。"""
        if not index_path.exists():
            return []
        try:
            index_payload = json.loads(index_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise ReportArchiveLoadError(f"读取归档索引 {index_path} 失败：{error}") from error
        return [ReportArchiveSummary(**item) for item in index_payload]

    def _write_index(self, index_path: Path, history_items: list[ReportArchiveSummary]) -> None:
        """_write_index 写入归档索引。"""
        # 1. 索引使用原子替换写入，避免进程中断时留下半截 JSON。
        self._write_json_file(
            index_path,
            [item.model_dump() for item in history_items],
            "归档索引",
        )

    @staticmethod
    def _write_json_file(file_path: Path, payload: object, file_label: str) -> None:
        """_write_json_file 原子写入 JSON 文件，避免并发或中断造成脏文件。"""
        temp_path = file_path.with_name(f"{file_path.name}.tmp")
        try:
            temp_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            temp_path.replace(file_path)
        except (OSError, TypeError, ValueError) as error:
            try:
                if temp_path.exists():
                    temp_path.unlink()
            except OSError:
                pass
            raise ReportArchiveSaveError(f"写入{file_label} {file_path} 失败：{error}") from error
