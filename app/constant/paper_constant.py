"""paper_constant 常量定义。"""

ARXIV_API_URL = "http://export.arxiv.org/api/query"
OPENALEX_API_URL = "https://api.openalex.org/works"
DEFAULT_MAX_PAPER_COUNT = 5
DEFAULT_MAX_EVIDENCE_COUNT = 2
DEFAULT_REQUEST_TIMEOUT_SECONDS = 120
DEFAULT_MEMORY_PATH = "app/data/research_memory.json"
DEFAULT_LLM_MODEL = "gpt-4.1-mini"
DEFAULT_SOURCE_SEARCH_LIMIT = 3
SEARCH_MAX_WORKERS = 6
DEFAULT_MAX_FULL_TEXT_PAPER_COUNT = 2
DEFAULT_FULL_TEXT_PAGE_LIMIT = 12
DEFAULT_FULL_TEXT_CHUNK_CHAR_LIMIT = 1200
DEFAULT_FULL_TEXT_MIN_TEXT_LENGTH = 500
FULL_TEXT_SOURCE_ABSTRACT = "abstract"
FULL_TEXT_SOURCE_PDF = "pdf"

# 标准化的论文章节类别（统一映射后的内部 section_kind）
SECTION_KIND_ABSTRACT = "abstract"
SECTION_KIND_INTRODUCTION = "introduction"
SECTION_KIND_RELATED_WORK = "related_work"
SECTION_KIND_METHOD = "method"
SECTION_KIND_EXPERIMENT = "experiment"
SECTION_KIND_RESULT = "result"
SECTION_KIND_DISCUSSION = "discussion"
SECTION_KIND_CONCLUSION = "conclusion"
SECTION_KIND_OTHER = "other"

# section 标题的正则匹配规则（按 kind 聚合，匹配时不区分大小写）
SECTION_HEADING_PATTERNS: list[tuple[str, str]] = [
    (SECTION_KIND_ABSTRACT, r"^\s*abstract\b"),
    (SECTION_KIND_INTRODUCTION, r"^\s*(?:\d+[\.\s]+)?introduction\b"),
    (SECTION_KIND_RELATED_WORK, r"^\s*(?:\d+[\.\s]+)?(?:related\s+work|background|preliminaries|prior\s+work)\b"),
    (SECTION_KIND_METHOD, r"^\s*(?:\d+[\.\s]+)?(?:method(?:ology|s)?|approach|model|proposed\s+method|our\s+method|architecture|framework|algorithm|design)\b"),
    (SECTION_KIND_EXPERIMENT, r"^\s*(?:\d+[\.\s]+)?(?:experiment(?:s|al\s+setup)?|evaluation|implementation|setup|datasets?|empirical\s+study)\b"),
    (SECTION_KIND_RESULT, r"^\s*(?:\d+[\.\s]+)?(?:results?|findings|main\s+results)\b"),
    (SECTION_KIND_DISCUSSION, r"^\s*(?:\d+[\.\s]+)?(?:discussion|analysis|ablation(?:\s+study|s)?|case\s+study|limitations?)\b"),
    (SECTION_KIND_CONCLUSION, r"^\s*(?:\d+[\.\s]+)?(?:conclusion|conclusions|conclud(?:e|ing)\s+remarks|summary|future\s+work)\b"),
]

# section 优先级权重（用于抽取上下文挑选 chunk，权重越大越优先）
SECTION_KIND_PRIORITY: dict[str, int] = {
    SECTION_KIND_METHOD: 5,
    SECTION_KIND_RESULT: 5,
    SECTION_KIND_EXPERIMENT: 4,
    SECTION_KIND_CONCLUSION: 4,
    SECTION_KIND_DISCUSSION: 3,
    SECTION_KIND_ABSTRACT: 2,
    SECTION_KIND_INTRODUCTION: 1,
    SECTION_KIND_RELATED_WORK: 0,
    SECTION_KIND_OTHER: 0,
}

# 单篇抽取上下文每个章节最多保留的 chunk 数
DEFAULT_FULL_TEXT_CONTEXT_PER_SECTION = 1
# 单篇抽取上下文允许的总 chunk 数上限
DEFAULT_FULL_TEXT_CONTEXT_MAX_CHUNKS = 5
# 长文双段抽取阈值：page_count 超过该值或 chunk 数超过该值时启用
LONG_PAPER_PAGE_THRESHOLD = 16
LONG_PAPER_CHUNK_THRESHOLD = 12
# 长文双段抽取每段允许的最大 chunk 数（method 段 + results 段各取一段）
LONG_PAPER_SEGMENT_MAX_CHUNKS = 4

# ── 引文图 PageRank-lite 重排 ──
# 用于重排时的引用阻尼系数（PageRank 经典 0.85，这里裁剪为更平滑的 0.7）
PAGERANK_LITE_DAMPING = 0.7
# 引用对数缩放后再做 min-max 归一化，避免单篇高引霸榜
PAGERANK_LITE_LOG_BASE = 10.0
# PageRank-lite 分量在最终排序中的权重（与 source/summary 等基础分并列）
PAGERANK_LITE_WEIGHT = 1.0

PAPER_SOURCE_ARXIV = "arxiv"
PAPER_SOURCE_OPENALEX = "openalex"
PAPER_SOURCE_SEMANTIC_SCHOLAR = "semantic_scholar"
PAPER_SOURCE_CROSSREF = "crossref"

PAPER_SOURCE_PRIORITY = {
    PAPER_SOURCE_SEMANTIC_SCHOLAR: 4,
    PAPER_SOURCE_OPENALEX: 3,
    PAPER_SOURCE_CROSSREF: 2,
    PAPER_SOURCE_ARXIV: 1,
}

# ── 主题相关性评分 ──
PAPER_RELEVANCE_TITLE_WEIGHT = 0.55
PAPER_RELEVANCE_SUMMARY_WEIGHT = 0.30
PAPER_RELEVANCE_PHRASE_WEIGHT = 0.15
PAPER_RELEVANCE_MIN_KEEP_SCORE = 0.12
PAPER_RELEVANCE_FALLBACK_KEEP_RATIO = 0.5
PAPER_RELEVANCE_KEYWORD_STOPWORDS = {
    "and", "are", "for", "from", "into", "that", "the", "this", "with",
    "using", "based", "via", "towards", "toward", "study", "survey",
    "analysis", "research", "paper", "papers", "large", "language",
    "model", "models", "llm", "llms",
}

COMPARISON_DIMENSION_METHOD = "方法思想"
COMPARISON_DIMENSION_DATASET = "实验设置"
COMPARISON_DIMENSION_ADVANTAGE = "优势"
COMPARISON_DIMENSION_LIMITATION = "局限"
COMPARISON_DIMENSION_SCENARIO = "适用场景"

DEFAULT_COMPARISON_DIMENSIONS = [
    COMPARISON_DIMENSION_METHOD,
    COMPARISON_DIMENSION_DATASET,
    COMPARISON_DIMENSION_ADVANTAGE,
    COMPARISON_DIMENSION_LIMITATION,
    COMPARISON_DIMENSION_SCENARIO,
]

FOCUS_AREA_KEYWORDS = {
    "benchmark": ["benchmark", "evaluation", "leaderboard", "metric"],
    "repair": ["repair", "fix", "bug", "debug", "program repair"],
    "agent": ["agent", "tool", "planning", "reasoning"],
    "retrieval": ["retrieval", "rag", "search", "index"],
    "safety": ["safety", "hallucination", "faithful", "reliable"],
    "multimodal": ["vision", "multimodal", "image", "video"],
}

LIMITATION_HINTS = [
    "limited",
    "however",
    "challenge",
    "future work",
    "cost",
    "latency",
    "generalization",
    "depends on",
    "trade-off",
]
