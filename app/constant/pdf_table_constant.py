"""pdf_table_constant PDF 表格抽取相关常量。"""

# PDF 表格抽取页数上限，避免在长论文上耗费过多时间
PDF_TABLE_PAGE_LIMIT = 10

# 单篇论文最多抽取的表格行数（防止综述类论文溢出）
PDF_TABLE_MAX_RESULT_ROWS = 30

# 表格表头识别中可作为方法列的关键词
PDF_TABLE_METHOD_HEADER_KEYWORDS = (
    "method",
    "model",
    "approach",
    "system",
)

# 表格表头识别中可作为指标列的关键词
PDF_TABLE_METRIC_HEADER_KEYWORDS = (
    "accuracy",
    "f1",
    "bleu",
    "rouge",
    "score",
    "ppl",
    "em",
    "exact",
    "pass@",
)
