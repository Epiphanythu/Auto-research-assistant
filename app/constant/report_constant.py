"""report_constant 报告归档常量。"""

DEFAULT_REPORT_ARCHIVE_DIR = "app/data/report_archive"
DEFAULT_REPORT_ARCHIVE_INDEX_FILE = "index.json"
DEFAULT_REPORT_HISTORY_LIMIT = 12
REPORT_ID_PATTERN = r"^report-\d{8}-\d{6}-[0-9a-f]{8}$"

# ── 导出 Markdown 报告 ──
EXPORT_FORMAT_MARKDOWN = "md"
EXPORT_FORMAT_JSON = "json"
SUPPORTED_EXPORT_FORMATS = (EXPORT_FORMAT_MARKDOWN, EXPORT_FORMAT_JSON)
MARKDOWN_MEDIA_TYPE = "text/markdown; charset=utf-8"
JSON_MEDIA_TYPE = "application/json; charset=utf-8"

# 支持度文案映射
SUPPORT_LEVEL_TEXTS = {
    "supported": "支持充分",
    "partial": "支持部分充分",
    "unsupported": "暂未支持",
}

# 审查结论文案映射
VERDICT_TEXTS = {
    "overall_pass": "可直接使用",
    "revise": "建议修订",
    "blocked": "暂不通过",
}
