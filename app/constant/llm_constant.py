"""llm_constant 大模型相关常量。"""

# 缓存目录与文件
DEFAULT_LLM_CACHE_DIR = "app/data/llm_cache"
LLM_CACHE_FILE_SUFFIX = ".json"

# 缓存键参与字段
LLM_CACHE_KEY_FIELDS = ("model", "system_prompt", "user_prompt", "temperature")

# 结构化日志事件名
LLM_EVENT_REQUEST = "llm.request"
LLM_EVENT_SUCCESS = "llm.success"
LLM_EVENT_FAILURE = "llm.failure"
LLM_EVENT_CACHE_HIT = "llm.cache_hit"
LLM_EVENT_CACHE_WRITE = "llm.cache_write"

# 图节点结构化日志事件名（与 LLM 事件区分前缀，便于日志平台分流）
GRAPH_EVENT_NODE_START = "graph.node_start"
GRAPH_EVENT_NODE_COMPLETE = "graph.node_complete"
GRAPH_EVENT_NODE_SKIP = "graph.node_skip"
