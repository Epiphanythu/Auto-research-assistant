# AGENTS.md

## 必需配置

复制 `.env.example` 为 `.env` 并填入实际值：

```bash
cp .env.example .env
```

| 变量 | 必需 | 说明 |
|------|------|------|
| `LLM_BASE_URL` | 是 | OpenAI 兼容 API 地址 |
| `LLM_API_KEY` | 是 | API 密钥 |
| `LLM_MODEL` | 是 | 模型名称（如 `glm-4-flash`、`gpt-4o-mini`） |
| `LOG_LEVEL` | 否 | 日志级别，默认 `INFO` |
| `REPORT_ARCHIVE_DIR` | 否 | 报告归档目录，默认 `app/data/report_archive` |

外部数据源（无需配置 API Key，但有频率限制）：
- Semantic Scholar — 每 5 秒 1 次请求
- OpenAlex — 无限制
- arXiv — 有请求间隔要求
- CrossRef — 有请求间隔要求

## 环境管理

统一使用 **uv** 管理 Python 环境和依赖。

```bash
# 安装依赖
uv sync

# 添加新依赖
uv add <包名>

# 添加开发依赖
uv add --dev <包名>

# 通过 uv 执行命令
uv run python -m pytest
uv run python -m app.main
uv run uvicorn app.main:app --reload
```

禁止直接使用 `pip install`。所有依赖变更必须通过 `uv add`，确保 `pyproject.toml` 和 `uv.lock` 同步。

## Git 规范

- **提交信息** 采用 Conventional Commits 格式：
  - `feat: <描述>` — 新功能
  - `fix: <描述>` — 缺陷修复
  - `refactor: <描述>` — 重构（不改变行为）
  - `docs: <描述>` — 仅文档变更
  - `test: <描述>` — 新增或更新测试
  - `chore: <描述>` — 构建、配置、工具链变更
- **带作用域示例**：`feat(pipeline): 新增研究空白检测阶段`、`fix(api): 处理 SSE 超时`
- 按逻辑单元提交——每次提交对应一个完整改动，而非一个文件。
- 禁止使用 `--no-verify` 跳过钩子。钩子失败时排查根因并修复。

## 项目结构

```
app/
├── clients/            # 外部 API 客户端（Semantic Scholar、OpenAlex、arXiv、CrossRef）
├── constant/           # 常量（论文来源、提示词模板、报告配置）
├── middleware/         # FastAPI 中间件（限流等）
├── models/             # Pydantic 数据模型
├── services/
│   ├── core/           # 核心服务：LLM 调用、多源搜索、研究图编排、报告生成
│   ├── pipeline/       # 流水线阶段：信息抽取、证据质量、审稿评估
│   ├── analysis/       # 分析功能：趋势分析、论文推荐
│   └── infrastructure/ # 基础设施：记忆存储、报告归档、全文提取、搜索缓存
frontend/
├── src/
│   ├── components/     # React 组件
│   ├── hooks/          # 自定义 React Hooks
│   ├── pages/          # 页面级组件
│   ├── store/          # Zustand 状态管理
│   ├── types/          # TypeScript 类型定义
│   └── utils/          # API 工具函数
tests/                  # 后端测试
```

## 导入路径

服务层已按职责拆分为子包，请使用新路径导入：

```python
# 核心服务
from app.services.core.llm_service import LLMService
from app.services.core.search_service import SearchService
from app.services.core.report_service import ReportService
from app.services.core.research_graph import ResearchGraph

# 流水线阶段
from app.services.pipeline.extraction_service import ExtractionService
from app.services.pipeline.evidence_quality_service import EvidenceQualityService
from app.services.pipeline.reviewer_service import ReviewerService

# 分析服务
from app.services.analysis.trend_analysis_service import TrendAnalysisService
from app.services.analysis.recommendation_service import RecommendationService

# 基础设施服务
from app.services.infrastructure.memory_service import MemoryService
from app.services.infrastructure.report_archive_service import ReportArchiveService
from app.services.infrastructure.full_text_service import FullTextService
from app.services.infrastructure.search_cache import SearchCache, get_search_cache
```
