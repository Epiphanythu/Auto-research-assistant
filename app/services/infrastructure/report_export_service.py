"""report_export_service 研究报告导出服务（Markdown / JSON）。"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import List

from app.constant.report_constant import (
    SUPPORT_LEVEL_TEXTS,
    VERDICT_TEXTS,
)
from app.models.research_models import (
    ClaimFactCheck,
    ClaimReliability,
    DebateRound,
    PaperInsight,
    ResearchReport,
)


class ReportExportService:
    """ReportExportService 将 ResearchReport 渲染为可下载文本。"""

    # ── 公开 API ──────────────────────────────────────────────────────────

    def render_markdown(self, report: ResearchReport) -> str:
        """render_markdown 把研究报告渲染为完整 Markdown 文本。"""
        # 1. 顶部摘要：标题、时间、审查结论
        sections: list[str] = []
        sections.append(self._render_header(report))
        sections.append(self._render_review(report))
        # 2. 辩论与可靠性评估
        sections.append(self._render_debate(report.debate_log))
        sections.append(self._render_reliability(report))
        # 3. Fact-Check 报告（Phase 3 引入，可选）
        sections.append(self._render_fact_check(report))
        sections.append(self._render_contradictions(report))
        # 4. 研究空白与综述主体
        sections.append(self._render_gaps(report))
        sections.append(self._render_overview(report))
        # 5. 研究笔记 / 后续 / 论文洞察
        sections.append(self._render_research_note(report))
        sections.append(self._render_next_actions(report))
        sections.append(self._render_paper_insights(report.insights))
        # 6. LLM 调用统计（t9/t8 统计字段，可选）
        sections.append(self._render_llm_stats(report))
        return "\n".join(part for part in sections if part).rstrip() + "\n"

    def render_json(self, report: ResearchReport) -> str:
        """render_json 把研究报告渲染为格式化 JSON 文本。"""
        return json.dumps(report.model_dump(), ensure_ascii=False, indent=2)

    def build_filename(self, report: ResearchReport, suffix: str) -> str:
        """build_filename 生成统一的导出文件名。"""
        topic = report.request.topic or "research-report"
        sanitized = self._sanitize(topic.lower()) or "research-report"
        return f"{sanitized}.{suffix}"

    # ── 内部渲染 ──────────────────────────────────────────────────────────

    def _render_header(self, report: ResearchReport) -> str:
        """_render_header 渲染头部信息。"""
        return "\n".join([
            f"# {report.request.topic} 研究报告",
            "",
            f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        ])

    def _render_review(self, report: ResearchReport) -> str:
        """_render_review 渲染审查结论区块。"""
        review = report.review_report
        verdict_text = VERDICT_TEXTS.get(review.verdict, review.verdict or "未标注")
        return "\n".join([
            "",
            "## 审查结论",
            f"- 结论：{verdict_text}",
            f"- 当前优势：{'；'.join(review.strengths) or '暂无'}",
            f"- 主要风险：{'；'.join(review.risks) or '暂无'}",
            f"- 修订建议：{'；'.join(review.revision_advice) or '暂无'}",
        ])

    def _render_debate(self, debate_log: List[DebateRound]) -> str:
        """_render_debate 渲染 Critic-Writer 辩论记录。"""
        if not debate_log:
            return "\n".join(["", "## Critic-Writer 辩论记录", "- 无辩论记录"])
        rounds = []
        for round_item in debate_log:
            weakness_lines = (
                "\n".join(f"  - [{w.severity}] {w.point}" for w in round_item.critic_weaknesses)
                if round_item.critic_weaknesses else "- 无弱点"
            )
            revision = f"\n- 修订说明：{round_item.revision_summary}" if round_item.revision_summary else ""
            rounds.append(
                f"### 第 {round_item.round_number} 轮\n"
                f"- 质量分：{round_item.critic_quality_score}/10\n"
                f"- 通过：{'是' if round_item.passed else '否'}\n"
                f"{weakness_lines}{revision}"
            )
        return "\n".join(["", "## Critic-Writer 辩论记录", "\n\n".join(rounds)])

    def _render_reliability(self, report: ResearchReport) -> str:
        """_render_reliability 渲染证据可靠性评估区块。"""
        reliability = report.synthesis_reliability
        if reliability is None:
            return "\n".join(["", "## 证据可靠性评估", "- 暂无"])
        claim_lines = self._format_claim_reliability(reliability.claims)
        return "\n".join([
            "",
            "## 证据可靠性评估",
            f"- 总体评分：{round(reliability.overall_score * 100)}%",
            f"- 强：{reliability.strong_count} / 中：{reliability.moderate_count} "
            f"/ 弱：{reliability.weak_count} / 孤立：{reliability.isolated_count}",
            "",
            claim_lines,
        ])

    def _render_fact_check(self, report: ResearchReport) -> str:
        """_render_fact_check 渲染 Fact-Check 报告区块。"""
        fact_check = report.fact_check_report
        if fact_check is None or fact_check.total_claims == 0:
            return ""
        item_lines = self._format_fact_check_items(fact_check.items)
        flagged = "；".join(fact_check.flagged_claims) or "暂无"
        return "\n".join([
            "",
            "## 论断事实校验",
            f"- 论断总数：{fact_check.total_claims}",
            f"- 支持充分：{fact_check.supported_count}",
            f"- 弱支撑：{fact_check.weak_count}",
            f"- 暂未支撑：{fact_check.unsupported_count}",
            f"- NLI 二次确认：{fact_check.nli_verified_count}",
            f"- 总体支撑率：{round(fact_check.overall_score * 100)}%",
            f"- 高风险论断：{flagged}",
            "",
            item_lines,
        ])

    def _render_contradictions(self, report: ResearchReport) -> str:
        """_render_contradictions 渲染跨论文矛盾区块。"""
        contradictions = getattr(report, "contradictions", None) or []
        if not contradictions:
            return ""
        # 1. 每条矛盾输出一段简表
        lines: list[str] = ["", "## 跨论文矛盾"]
        for idx, item in enumerate(contradictions, 1):
            lines.extend([
                f"### 矛盾 {idx}: {item.topic or '未命名议题'}",
                f"- 论断 A（{item.paper_id_a}）：{item.claim_a}",
                f"- 论断 B（{item.paper_id_b}）：{item.claim_b}",
                f"- 冲突说明：{item.rationale or '—'}",
                "",
            ])
        return "\n".join(lines)

    def _render_gaps(self, report: ResearchReport) -> str:
        """_render_gaps 渲染研究空白区块。"""
        comparison = report.comparison
        return "\n".join([
            "",
            "## 研究空白",
            f"- 是否建议补充：{'是' if comparison.need_follow_up else '否'}",
            f"- 判断说明：{comparison.gap_reasoning or '暂无说明'}",
            "- 待补充问题：",
            self._format_list(comparison.gaps),
            "- 建议检索方向：",
            self._format_list(comparison.follow_up_queries),
        ])

    def _render_overview(self, report: ResearchReport) -> str:
        """_render_overview 渲染综述主体区块。"""
        comparison = report.comparison
        idea_lines = (
            "\n".join(
                f"{index + 1}. {idea.title}：{idea.rationale}（实施注意：{idea.risk}）"
                for index, idea in enumerate(comparison.ideas)
            )
            if comparison.ideas else "- 暂无"
        )
        return "\n".join([
            "",
            "## 结构化综述",
            comparison.overview or "暂无综述。",
            "",
            "### 趋势",
            self._format_list(comparison.trends),
            "",
            "### 研究空白摘要",
            self._format_list(comparison.gaps),
            "",
            "### 创新建议",
            idea_lines,
        ])

    def _render_research_note(self, report: ResearchReport) -> str:
        """_render_research_note 渲染研究笔记区块。"""
        return "\n".join([
            "",
            "## 研究笔记",
            report.research_note or "暂无研究笔记。",
        ])

    def _render_next_actions(self, report: ResearchReport) -> str:
        """_render_next_actions 渲染后续事项区块。"""
        return "\n".join([
            "",
            "## 后续事项",
            self._format_list(report.next_actions),
        ])

    def _render_paper_insights(self, insights: List[PaperInsight]) -> str:
        """_render_paper_insights 渲染论文洞察区块。"""
        if not insights:
            return "\n".join(["", "## 论文洞察", "暂无论文洞察。"])
        blocks = []
        for index, insight in enumerate(insights):
            blocks.append(
                f"### {index + 1}. {insight.paper.title}\n"
                f"- 问题：{insight.problem}\n"
                f"- 方法：{insight.method}\n"
                f"- 创新：{insight.innovation}\n"
                f"- 发现：{insight.findings}\n"
                f"- 局限：{insight.limitation}"
            )
        return "\n".join(["", "## 论文洞察", "\n\n".join(blocks)])

    def _render_llm_stats(self, report: ResearchReport) -> str:
        """_render_llm_stats 渲染 LLM 调用统计区块（如有）。"""
        stats = report.llm_call_stats or {}
        if not stats:
            return ""
        return "\n".join([
            "",
            "## LLM 调用统计",
            f"- 调用次数：{stats.get('call_count', 0)}",
            f"- 缓存命中：{stats.get('cache_hit_count', 0)}",
            f"- prompt tokens：{stats.get('prompt_tokens', 0)}",
            f"- completion tokens：{stats.get('completion_tokens', 0)}",
            f"- total tokens：{stats.get('total_tokens', 0)}",
            f"- 总耗时：{stats.get('total_elapsed_ms', 0)} ms",
        ])

    # ── 辅助方法 ──────────────────────────────────────────────────────────

    @staticmethod
    def _format_list(items: List[str]) -> str:
        """_format_list 将列表渲染为 Markdown 条目。"""
        if not items:
            return "- 暂无"
        return "\n".join(f"- {item}" for item in items)

    @staticmethod
    def _format_claim_reliability(claims: List[ClaimReliability]) -> str:
        """_format_claim_reliability 渲染结论级可靠性条目。"""
        if not claims:
            return "- 暂无"
        return "\n".join(
            f"{index + 1}. {claim.claim}\n"
            f"   - 可靠性：{claim.reliability_level}（{claim.reliability_score}）\n"
            f"   - 说明：{claim.reasoning or '暂无说明'}"
            for index, claim in enumerate(claims)
        )

    @staticmethod
    def _format_fact_check_items(items: List[ClaimFactCheck]) -> str:
        """_format_fact_check_items 渲染 fact-check 单条详情。"""
        if not items:
            return "- 暂无"
        lines = []
        for index, item in enumerate(items):
            support_text = SUPPORT_LEVEL_TEXTS.get(item.support_level, item.support_level)
            nli_text = f"（NLI：{item.nli_verdict}）" if item.nli_verdict else ""
            lines.append(
                f"{index + 1}. {item.claim}\n"
                f"   - 支持度：{support_text}{nli_text}\n"
                f"   - 关键词重叠：{round(item.keyword_overlap_score * 100)}%\n"
                f"   - 评估：{item.reason or '暂无说明'}"
            )
        return "\n".join(lines)

    @staticmethod
    def _sanitize(text: str) -> str:
        """_sanitize 清理文件名中的特殊字符。"""
        cleaned = re.sub(r"[<>:\"/\\|?*\x00-\x1f]", "-", text)
        cleaned = re.sub(r"\s+", "-", cleaned)
        return cleaned[:80]
