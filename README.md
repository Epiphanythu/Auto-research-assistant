<p align="center">
  <img src="https://img.shields.io/badge/python-3.9+-blue.svg" alt="Python 3.9+">
  <img src="https://img.shields.io/badge/react-18-61dafb.svg" alt="React 18">
  <img src="https://img.shields.io/badge/fastapi-0.116+-009688.svg" alt="FastAPI">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="MIT License">
</p>

<h1 align="center">自动科研助手 Auto Research Assistant</h1>

<p align="center">
  <strong>多源检索 · 流水线编排 · 实时流式进度 · 趋势分析 · 论文推荐</strong><br>
  面向论文检索、阅读、对比与研究笔记生成的智能代理系统
</p>

---

## 功能特性

- **多源并行检索** — Semantic Scholar、OpenAlex、arXiv、CrossRef 四源并发，使用 ThreadPoolExecutor 聚合结果
- **结构化研究流水线** — 规划 → 检索 → 按研究单元分小节综合 → 多 Agent 辩论 → 审稿评估 → 论断校验 → 归档，全链路自动化
- **PDF 章节感知解析** — [FullTextService](file:///Users/bytedance/Desktop/LLM/app/services/infrastructure/full_text_service.py) 在 PDF 全文提取时识别 Abstract / Introduction / Method / Results / Discussion 等章节，按重要性优先采样证据，避免引言/参考文献噪声主导抽取上下文
- **按研究单元分小节综合** — [UnitSynthesisService](file:///Users/bytedance/Desktop/LLM/app/services/pipeline/unit_synthesis_service.py) 针对每个研究问题独立做 LLM 综合，再聚合为整体笔记，结果包含每个小节的方法、共识、矛盾、置信度
- **论断级 Fact-Check** — [FactCheckService](file:///Users/bytedance/Desktop/LLM/app/services/pipeline/fact_check_service.py) 对最终研究笔记做句子级切分，逐句与候选证据做中英混合关键词重叠打分，标注 strong / moderate / weak / unsupported 四级支撑度
- **Multi-Agent 辩论机制** — Critic Agent 审查研究综合的弱点与遗漏，Writer Agent 据此修订，最多 2 轮迭代，确保研究笔记的严谨性
- **三层证据可靠性框架** — 论文级方法学质量评估 → 结论级证据可靠性 → 综合级自评估，量化研究结论的可信度
- **SSE 实时推送** — 通过 Server-Sent Events 把每个阶段的进度、状态与论文发现即时推送到前端
- **研究趋势分析** — 年度论文产量、引用速度、热门 / 新兴方向自动识别
- **论文推荐引擎** — 基于论文相似度与主题匹配的多维推荐
- **报告自动归档** — 研究报告持久化存储于本地文件，支持历史回顾与跨报告对比
- **现代化前端** — React 18 + Tailwind CSS，支持 SSE 进度面板、报告详情、对比页面与趋势图表

## 系统架构

整体采用 **前端 SPA + FastAPI 后端 + LangGraph 状态机流水线** 的分层结构，通过 SSE 把流水线每个阶段的进度实时推送到前端。

### 分层视图

```mermaid
flowchart TB
    subgraph FE["前端层 · React 18 + TypeScript"]
        FE_Pages["Pages<br/>Home · Review · Evidence<br/>Trends · ReportDetail · Compare"]
        FE_Comp["Components<br/>ProgressPanel · PaperCard<br/>TrendChartView · ReportPanels"]
        FE_State["State / Hooks<br/>Zustand · useEventSource(SSE)"]
    end

    subgraph API["API 层 · FastAPI"]
        API_Endpoints["/research · /research/stream<br/>/reports · /trends · /recommendations"]
        API_Mid["CORS · RateLimitMiddleware (3 / 60s)<br/>APIError 统一异常处理"]
    end

    subgraph CORE["服务编排层 · services/core"]
        ReportService["ReportService<br/>报告编排（同步 + SSE 流）"]
        ResearchGraph["ResearchGraph (LangGraph)<br/>5 节点研究流水线"]
        LLMService["LLMService<br/>OpenAI 兼容 + 退避重试"]
        SearchService["SearchService<br/>多源并行检索 + 去重排序"]
    end

    subgraph PIPE["Pipeline 阶段"]
        Extraction[Extraction]
        EvidenceQ[EvidenceQuality]
        Reviewer[Reviewer]
    end

    subgraph ANA["Analysis 服务"]
        Trend[TrendAnalysis]
        Recom[Recommendation]
    end

    subgraph INFRA["Infrastructure"]
        Memory[MemoryService]
        Archive[ReportArchive]
        FullText[FullTextService]
        Cache[SearchCache]
    end

    subgraph CLIENT["External Clients"]
        SS[Semantic Scholar]
        OA[OpenAlex]
        AX[arXiv]
        CR[CrossRef]
    end

    FE -- "REST / SSE" --> API
    API --> CORE
    CORE --> PIPE
    CORE --> ANA
    CORE --> INFRA
    SearchService --> CLIENT
```

### 研究流水线状态机（LangGraph 7 节点）

[research_graph.py](file:///Users/bytedance/Desktop/LLM/app/services/core/research_graph.py) 使用 LangGraph 把研究流程编排为有向图，节点之间通过共享 `GraphState` 传递数据；当 `synthesize` 检测到研究空白且首轮迭代未结束时，会回到 `search` 节点做一次补充检索。

```mermaid
stateDiagram-v2
    [*] --> plan
    plan --> search : 关键词 + 研究单元
    search --> synthesize : papers + insights
    synthesize --> search : need_follow_up &amp;&amp; iter &lt; 1
    synthesize --> debate : continue
    debate --> review
    review --> fact_check
    fact_check --> finalize
    finalize --> [*]

    note right of plan
        1× LLM
        规划检索词 + 研究单元
    end note

    note right of search
        4 源并行检索
        + 章节感知 PDF 解析
        + 并行信息抽取
        ThreadPoolExecutor
    end note

    note right of synthesize
        按 ResearchUnit 并行小节综合
        + 全局聚合（research_note / trends / gaps / ideas）
        + 启发式空白检测
    end note

    note right of debate
        1-2× LLM/轮
        Critic-Writer 多轮辩论
        最多 2 轮
    end note

    note right of review
        2× LLM
        证据可靠性 + 质量审查
    end note

    note right of fact_check
        无 LLM
        论断级关键词重叠校验
        4 等级支撑度标注
    end note

    note right of finalize
        无 LLM
        持久化记忆 + 归档报告
    end note
```

| 节点 | 主要职责 | LLM 调用 |
|------|----------|----------|
| `plan` | 解析主题，生成检索关键词与研究单元 | 1× |
| `search` | 4 源并行检索 + 章节感知 PDF 解析 + 并行信息抽取 | 0（抽取阶段每篇论文 1×） |
| `synthesize` | 按 ResearchUnit 并行小节综合 + 全局聚合 + 启发式空白检测 | N+1×（N 为研究单元数） |
| `debate` | Critic-Writer 多轮辩论，Critic 审查弱点，Writer 修订研究笔记 | 1-2×/轮（最多 2 轮） |
| `review` | 证据可靠性评估、整体质量审查 | 2× |
| `fact_check` | 研究笔记句子级切分，与证据语料做关键词重叠打分，输出每条论断的支撑度 | 0 |
| `finalize` | 持久化记忆、归档报告（[ReportArchiveService](file:///Users/bytedance/Desktop/LLM/app/services/infrastructure/report_archive_service.py)） | 0 |

> 不支持 Mermaid 渲染的查看器（如部分 IDE）可参考下方 ASCII 简版。

<details>
<summary>ASCII 版流水线</summary>

```
START → plan ─→ search ─→ synthesize ─┬─(continue)─→ debate ─→ review ─→ fact_check ─→ finalize → END
                  ▲                    │
                  └──(need_follow_up,  │
                       iter < 1)───────┘
```

</details>

### 数据与可观测性

- **SSE 事件流**：每个节点开始/结束都会发 `stage_start` / `stage_complete` / `paper_found` / `error` 事件，前端 [useEventSource](file:///Users/bytedance/Desktop/LLM/frontend/src/hooks/useEventSource.ts) 解析后驱动 [ProgressPanel](file:///Users/bytedance/Desktop/LLM/frontend/src/components/ProgressPanel.tsx)。
- **本地持久化**：研究记忆与历史报告分别存于 `app/data/research_memory.json` 与 `app/data/report_archive/`（已加入 `.gitignore`）。
- **检索缓存**：[SearchCache](file:///Users/bytedance/Desktop/LLM/app/services/infrastructure/search_cache.py) 提供线程安全的内存缓存，避免重复请求外部数据源。
- **限流**：[RateLimitMiddleware](file:///Users/bytedance/Desktop/LLM/app/middleware/rate_limit.py) 对 `/api/v1/research*` 做 60 秒 3 次的限流，防止意外刷模型额度。

## 快速开始

### 环境要求

- Python 3.9+
- Node.js 18+
- 推荐使用 [uv](https://github.com/astral-sh/uv) 管理 Python 环境

### 1. 克隆与安装

```bash
git clone https://github.com/your-username/auto-research-assistant.git
cd auto-research-assistant

# 后端（推荐使用 uv）
uv sync

# 前端
cd frontend && npm install && cd ..
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，填入大模型相关凭证：

```env
LLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4   # 任意 OpenAI 兼容端点
LLM_API_KEY=your-api-key
LLM_MODEL=glm-4-flash                                 # 或 gpt-4o-mini 等
LOG_LEVEL=INFO
REPORT_ARCHIVE_DIR=app/data/report_archive            # 可选，报告归档目录
```

> 兼容任何 OpenAI 风格 API（OpenAI、智谱 GLM、DeepSeek、通义千问、本地 Ollama 等）。

### 3. 启动服务

```bash
# 终端 1 —— 后端
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 终端 2 —— 前端
cd frontend && npm run dev
```

打开 http://localhost:5173 即可开始调研。

## 项目结构

```
app/
├── clients/                    # 外部 API 客户端
│   ├── semantic_scholar_client.py
│   ├── openalex_client.py
│   ├── arxiv_client.py
│   └── crossref_client.py
├── constant/                   # 常量与提示词模板
├── middleware/                 # FastAPI 中间件（限流等）
├── models/                     # Pydantic 数据模型
├── services/
│   ├── core/                   # LLM 调用、多源搜索、研究图编排、报告生成
│   ├── pipeline/               # 流水线阶段：信息抽取、证据质量、审稿评估
│   ├── analysis/               # 趋势分析、论文推荐
│   └── infrastructure/         # 记忆存储、报告归档、全文提取、搜索缓存
├── main.py                     # FastAPI 入口
└── cli.py                      # 命令行入口
frontend/
├── src/
│   ├── components/             # React 组件
│   ├── hooks/                  # SSE 流式 Hook
│   ├── pages/                  # 页面级组件
│   ├── store/                  # Zustand 全局状态
│   ├── types/                  # TypeScript 类型定义
│   └── utils/                  # API 工具函数
tests/                          # 后端测试
```

## API 接口

### 研究

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/v1/research` | 同步生成研究报告 |
| `POST` | `/api/v1/research/stream` | 流式生成研究报告（SSE） |

### 报告归档

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/v1/reports` | 获取历史报告列表 |
| `GET` | `/api/v1/reports/{report_id}` | 获取指定历史报告 |

### 趋势与推荐

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/v1/trends/{topic}` | 分析研究主题的趋势 |
| `GET` | `/api/v1/recommendations/{paper_id}` | 基于单篇论文推荐 |
| `POST` | `/api/v1/recommendations/topic` | 基于研究主题推荐 |

### 健康检查

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/health` | 健康检查（含模型与缓存诊断信息） |

## 前端页面

| 路由 | 说明 |
|------|------|
| `/` | 调研工作台 —— 提交主题、查看 SSE 流式进度 |
| `/review` | 结构化文献综述 |
| `/evidence` | 证据集合与校验 |
| `/reports/:reportId` | 历史报告详情 |
| `/compare` | 跨报告对比 |
| `/trends` | 研究趋势分析与图表 |

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.9 · FastAPI · Pydantic v2 · ThreadPoolExecutor |
| 前端 | React 18 · TypeScript · Vite · Zustand · Tailwind CSS |
| 数据源 | Semantic Scholar · OpenAlex · arXiv · CrossRef |
| 大模型 | OpenAI 兼容 API，支持指数退避重试 |

## 测试

```bash
uv run python -m pytest tests/ -v
```

## 许可证

MIT
