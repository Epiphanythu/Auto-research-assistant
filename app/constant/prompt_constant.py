"""prompt_constant 提示词常量。"""

SYSTEM_PROMPT_RESEARCH_ASSISTANT = (
    "你是一个自动科研助手。请严格基于输入论文信息输出结构化内容，"
    "避免编造论文中不存在的结论，并优先给出证据化、可比对的表述。"
)

EXTRACTION_PROMPT_TEMPLATE = """
请基于以下论文标题、摘要与可用的正文候选片段，输出 JSON 对象，不要输出额外解释。

标题：{title}
摘要：{summary}
正文候选片段：{full_text_context}

字段要求：
1. problem: 论文要解决的问题
2. method: 核心方法
3. innovation: 主要创新点
4. findings: 核心实验结论
5. limitation: 可能局限
6. confidence: 0 到 1 之间的小数，表示信息完整度和结论可信度
7. quantitative_results: 数组，提取论文中的定量实验结果，每项包含：
   - dataset: 使用的数据集名称
   - metric: 评价指标（如 Accuracy、F1、BLEU 等）
   - value: 报告的具体数值
   - baseline: 对比的基线方法名称（如有）
   如果论文未提供定量结果，返回空数组
8. quality_metrics: 对象，评估论文的方法学质量：
   - study_design: 实验设计类型，取值之一：controlled_experiment / ablation / observational / theoretical / benchmark / survey / unspecified
   - data_availability: 数据可得性，取值之一：public / private / synthetic / unspecified
   - reproducibility: 可复现性，取值之一：code_public / code_partial / code_unavailable / unspecified
   - baseline_fairness: 基线对比公平性，取值之一：standard_baselines / weak_baselines / no_comparison / unspecified
   - metric_type: 指标类型，取值之一：standard / custom / mixed / unspecified
   - note: 一句话说明质量评估依据
""".strip()

PLAN_AND_SUPERVISE_PROMPT_TEMPLATE = """
请基于以下研究简报，一次性输出 JSON 对象，不要输出额外解释。

主题：{topic}
目标：{research_goal}
关键问题：{key_questions}

字段要求：
1. normalized_topic: 规范化主题表述
2. search_keywords: 检索关键词数组（最多 4 个，必须使用英文，因为论文数据库均为英文）
   - 关键约束：每个关键词必须是**保留主题复合语义的组合短语**，禁止把主题中的多个核心概念拆开成单一宽泛词
   - 反例（禁止）："Large Language Models"、"Software Bug Fixing"、"Code LLMs"，这类宽泛词会召回大量无关论文
   - 正例：当主题为"代码大模型自动程序修复"时，应输出 "LLM-based automated program repair"、"large language model program repair"、"code repair with LLM"、"neural program repair with pretrained models"
   - 必须确保每个关键词同时包含主题中的两个或以上核心概念（例如 模型类别 + 任务类型）
3. focus_areas: 研究关注维度数组
4. research_units: 数组，每项包含 unit_id、question、focus、search_queries（必须使用英文，同样遵循组合短语约束）、completion_definition
""".strip()

COMPARE_AND_WRITE_PROMPT_TEMPLATE = """
请基于以下多篇论文的结构化信息，一次性输出 JSON 对象，不要输出额外解释。

研究主题：{topic}
论文信息：{paper_payload}

字段要求：
1. overview: 方向总体概览
2. trends: 研究趋势数组
3. gaps: 尚未被充分解决的问题数组
4. ideas: 可继续研究的创新方向数组，每项包含 title、rationale、risk
5. research_note: 一段 200 到 400 字的中文研究笔记
6. next_actions: 后续行动建议数组，3 到 5 项
""".strip()


# ─── Unit-level Synthesis (Phase 2) ───

UNIT_SYNTHESIS_PROMPT_TEMPLATE = """
你正在针对一个具体的研究问题，基于已抽取出的相关论文信息生成"该问题的小节综合"。
你的输出必须**严格基于提供的论文证据**，禁止编造论文中不存在的细节。

研究主题：{topic}
本节研究问题：{question}
本节关注重点：{focus}

候选论文（已按相关性筛选）：
{insights_payload}

请输出 JSON 对象，字段要求（全部使用中文）：
1. summary: 200 到 350 字，针对该研究问题给出有结构、有证据指向的回答；尽量提及具体论文标题。
2. key_methods: 数组，3 到 6 项，列出回答此问题时涉及的核心方法/技术。
3. consensus: 数组，列出多篇论文达成共识的结论；若没有共识请返回空数组。
4. disagreements: 数组，列出论文之间的矛盾或差异；若无矛盾请返回空数组。
5. supporting_paper_ids: 数组，列出真正被你引用过的论文 paper_id（来自候选论文）。
6. open_questions: 数组，2 到 4 项，列出该研究问题下尚未解决的子问题。
7. confidence: 0 到 1 的小数，反映你对本节综合的可信程度（依据：候选论文数量、是否覆盖核心方法、是否存在矛盾）。
""".strip()


GLOBAL_SYNTHESIS_PROMPT_TEMPLATE = """
你已为一个研究主题完成了多个研究问题的小节综合。请基于这些小节，生成"研究主题级"的整体笔记。
不得引入小节中不存在的新结论；可以做整合与比较。

研究主题：{topic}

各研究问题的小节综合（JSON 列表）：
{units_payload}

请输出 JSON 对象，字段要求（全部使用中文）：
1. overview: 方向总体概览
2. trends: 研究趋势数组（基于小节中的 consensus / key_methods 归纳）
3. gaps: 研究空白数组（基于小节中的 open_questions / disagreements 归纳）
4. ideas: 可继续研究的创新方向数组，每项包含 title、rationale、risk
5. research_note: 一段 250 到 450 字的中文研究笔记，按研究问题分段或分点
6. next_actions: 后续行动建议数组，3 到 5 项
""".strip()


REVIEW_PROMPT_TEMPLATE = """
请基于以下研究报告内容，输出 JSON 对象，不要输出额外解释。

研究主题：{topic}
研究笔记：{research_note}
研究空白：{gaps}
后续建议：{next_actions}

字段要求：
1. verdict: overall_pass 或 revision_needed
2. strengths: 优势数组
3. risks: 风险数组
4. revision_advice: 修订建议数组
""".strip()

# ─── Multi-Agent Debate Prompts ───

CRITIC_PROMPT_TEMPLATE = """
你是一个严谨的学术评审者（Critic）。请审查以下研究综合，找出其中的弱点、矛盾和遗漏。

研究主题：{topic}

研究笔记：
{research_note}

比较结论：
{comparison_payload}

可用论文洞察：
{insights_payload}

请输出 JSON 对象，字段要求：
1. weaknesses: 数组，每项包含：
   - point: 具体的问题描述
   - severity: high / medium / low
   - suggestion: 改进建议
   重点关注：无证据支撑的结论、过度泛化、忽略矛盾数据、缺少关键方法比较
2. overall_quality: 1 到 10 的整数（10为最高）
3. pass: 布尔值，true 表示质量可接受无需修订
最多输出 5 个最重要的弱点。如果质量足够好，可以返回空的 weaknesses 数组和 pass=true。
""".strip()

DEBATE_REVISION_PROMPT_TEMPLATE = """
你是一个研究综合撰写者（Writer）。Critic 对你的研究笔记提出了以下批评，请据此修订。

研究主题：{topic}

原始研究笔记：
{research_note}

原始比较结论（概览/趋势/空白）：
{comparison_payload}

Critic 的批评意见：
{critic_feedback}

请输出 JSON 对象，字段要求：
1. research_note: 修订后的研究笔记（200-400字中文）
2. overview: 修订后的方向概览（如有需要）
3. trends: 修订后的研究趋势数组（如有需要）
4. gaps: 修订后的研究空白数组（如有需要）
5. next_actions: 修订后的后续行动建议数组
6. revision_summary: 一句话说明你做了哪些修改
""".strip()


# ─── Fact-Check NLI Prompt (Phase 4) ───

FACT_CHECK_NLI_PROMPT_TEMPLATE = """
你是一个严谨的论断校验员。给定一条研究综合中的"论断"和若干来自候选论文的"证据片段"，
请判断证据是否能支撑该论断。注意：

- entailment：证据明确支撑该论断
- contradiction：证据明确反驳该论断
- neutral：证据与论断无直接关系，或不足以支撑

论断：
{claim}

候选证据片段（已截断）：
{evidence_payload}

请输出 JSON 对象，字段要求：
1. verdict: entailment / contradiction / neutral 三选一
2. rationale: 一句话说明判断依据，不超过 80 字
""".strip()


# ─── Self-Query 检索改写 Prompt ───

SELF_QUERY_PROMPT_TEMPLATE = """
你是检索查询改写助手。给定研究主题和已有关键词，生成 3~5 条不同视角的英文检索查询，
用于学术搜索引擎（如 arXiv / Semantic Scholar / OpenAlex / CrossRef）。

要求：
- 每条查询长度控制在 3~10 个词
- **每条查询必须保留研究主题的复合语义**，即同时包含主题中的两个或以上核心概念，避免输出"Large Language Models"、"Software Bug Fixing"这类单一宽泛词
- 至少包含一条侧重 "method"（方法/模型/算法）的查询
- 至少包含一条侧重 "evaluation/benchmark"（数据集/指标/对比）的查询
- 至少包含一条侧重 "survey/limitation/challenge"（综述/局限/挑战）的查询
- 不要重复输入中的原关键词，应给出有补充价值的新表述

研究主题：{topic}
已有关键词：{existing_keywords}

请输出 JSON 对象：
{{"queries": ["query1", "query2", "query3", ...]}}
""".strip()


# ─── 跨论文矛盾识别 Prompt ───

CONTRADICTION_PROMPT_TEMPLATE = """
你是研究综述的矛盾分析员。给定多条来源不同论文的论断（含 paper_id 与原文片段），
请识别其中"互相矛盾或观点冲突"的论断对，并给出冲突维度。

注意：
- 仅当两条论断在同一议题（同方法 / 同数据集 / 同结论指标）上做出方向相反的陈述时才算矛盾
- 字面相似但只是不同子任务 / 不同实验设置则不算矛盾
- 若全部论断观点一致，可返回空数组

候选论断：
{claims_payload}

请输出 JSON 对象：
{{
  "contradictions": [
    {{
      "topic": "冲突议题（如 \"是否有助于代码修复\"）",
      "claim_a_id": "...",
      "claim_b_id": "...",
      "rationale": "一句话说明冲突点，不超过 80 字"
    }}
  ]
}}
""".strip()
