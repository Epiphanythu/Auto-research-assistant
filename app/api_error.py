"""api_error API 错误定义。"""

from __future__ import annotations


class APIError(Exception):
    """APIError 统一封装接口层可返回的结构化错误。"""

    def __init__(
        self,
        status_code: int,
        error_code: str,
        title: str,
        detail: str,
        suggestion: str,
    ) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.error_code = error_code
        self.title = title
        self.detail = detail
        self.suggestion = suggestion

    def to_dict(self) -> dict[str, str | int]:
        """to_dict 转换为接口返回结构。"""
        return {
            "error_code": self.error_code,
            "title": self.title,
            "detail": self.detail,
            "suggestion": self.suggestion,
        }


class SearchSourceUnavailableError(APIError):
    """SearchSourceUnavailableError 学术检索源调用失败。"""

    def __init__(self, source_name: str, detail: str) -> None:
        super().__init__(
            status_code=502,
            error_code="search_source_unavailable",
            title="学术检索源不可用",
            detail=f"{source_name} 检索失败：{detail}",
            suggestion="请检查外部学术检索源的可访问性、网络状态和接口返回是否正常。",
        )


class SearchResponseParseError(APIError):
    """SearchResponseParseError 学术检索结果解析失败。"""

    def __init__(self, source_name: str, detail: str) -> None:
        super().__init__(
            status_code=502,
            error_code="search_response_invalid",
            title="检索结果解析失败",
            detail=f"{source_name} 返回的数据无法解析：{detail}",
            suggestion="请检查检索源接口是否发生变更，或稍后重试。",
        )


class SearchAggregationError(APIError):
    """SearchAggregationError 聚合检索阶段失败。"""

    def __init__(self, detail: str, suggestion: str) -> None:
        super().__init__(
            status_code=502,
            error_code="search_aggregation_failed",
            title="文献检索失败",
            detail=detail,
            suggestion=suggestion,
        )


class MemoryLoadError(APIError):
    """MemoryLoadError 记忆加载失败。"""

    def __init__(self, detail: str) -> None:
        super().__init__(
            status_code=500,
            error_code="memory_load_failed",
            title="历史记忆读取失败",
            detail=detail,
            suggestion="请检查记忆文件是否损坏、路径是否可访问，必要时清理本地记忆文件后重试。",
        )


class MemorySaveError(APIError):
    """MemorySaveError 记忆保存失败。"""

    def __init__(self, detail: str) -> None:
        super().__init__(
            status_code=500,
            error_code="memory_save_failed",
            title="历史记忆写入失败",
            detail=detail,
            suggestion="请检查记忆文件目录权限和磁盘状态，然后重新提交研究任务。",
        )


class FullTextDownloadError(APIError):
    """FullTextDownloadError PDF 下载失败。"""

    def __init__(self, paper_id: str, detail: str) -> None:
        super().__init__(
            status_code=502,
            error_code="full_text_download_failed",
            title="正文下载失败",
            detail=f"论文 {paper_id} 的 PDF 下载失败：{detail}",
            suggestion="请检查论文链接是否有效，以及目标站点是否可访问。",
        )


class FullTextParseError(APIError):
    """FullTextParseError PDF 解析失败。"""

    def __init__(self, paper_id: str, detail: str) -> None:
        super().__init__(
            status_code=502,
            error_code="full_text_parse_failed",
            title="正文解析失败",
            detail=f"论文 {paper_id} 的 PDF 解析失败：{detail}",
            suggestion="请检查 PDF 内容是否完整，或稍后重试其他可用论文。",
        )


class FullTextBatchError(APIError):
    """FullTextBatchError 全文批处理阶段失败。"""

    def __init__(self, detail: str) -> None:
        super().__init__(
            status_code=502,
            error_code="full_text_batch_failed",
            title="正文解析不可用",
            detail=detail,
            suggestion="请检查 PDF 链接、网络状态和解析依赖是否正常，或先关闭全文解析后重试。",
        )


class ReportArchiveLoadError(APIError):
    """ReportArchiveLoadError 报告归档读取失败。"""

    def __init__(self, detail: str) -> None:
        super().__init__(
            status_code=500,
            error_code="report_archive_load_failed",
            title="报告归档读取失败",
            detail=detail,
            suggestion="请检查归档目录和索引文件是否可访问，必要时修复归档文件后重试。",
        )


class ReportArchiveSaveError(APIError):
    """ReportArchiveSaveError 报告归档写入失败。"""

    def __init__(self, detail: str) -> None:
        super().__init__(
            status_code=500,
            error_code="report_archive_save_failed",
            title="报告归档写入失败",
            detail=detail,
            suggestion="请检查归档目录权限和磁盘状态，确保报告可以正常落盘保存。",
        )


class ArchivedReportNotFoundError(APIError):
    """ArchivedReportNotFoundError 指定归档报告不存在。"""

    def __init__(self, report_id: str) -> None:
        super().__init__(
            status_code=404,
            error_code="archived_report_not_found",
            title="历史报告不存在",
            detail=f"未找到编号为 {report_id} 的历史报告。",
            suggestion="请刷新历史记录列表后重试，或重新生成新的研究报告。",
        )
