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
3. focus_areas: 研究关注维度数组
4. research_units: 数组，每项包含 unit_id、question、focus、search_queries（必须使用英文）、completion_definition
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
