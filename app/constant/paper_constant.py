"""paper_constant 常量定义。"""

ARXIV_API_URL = "http://export.arxiv.org/api/query"
OPENALEX_API_URL = "https://api.openalex.org/works"
DEFAULT_MAX_PAPER_COUNT = 5
DEFAULT_MAX_EVIDENCE_COUNT = 2
DEFAULT_REQUEST_TIMEOUT_SECONDS = 120
DEFAULT_MEMORY_PATH = "app/data/research_memory.json"
DEFAULT_LLM_MODEL = "gpt-4.1-mini"
DEFAULT_SOURCE_SEARCH_LIMIT = 3
DEFAULT_MAX_FULL_TEXT_PAPER_COUNT = 2
DEFAULT_FULL_TEXT_PAGE_LIMIT = 8
DEFAULT_FULL_TEXT_CHUNK_CHAR_LIMIT = 1200
DEFAULT_FULL_TEXT_MIN_TEXT_LENGTH = 500
FULL_TEXT_SOURCE_ABSTRACT = "abstract"
FULL_TEXT_SOURCE_PDF = "pdf"

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
