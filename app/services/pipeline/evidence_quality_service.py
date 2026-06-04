"""evidence_quality_service 证据可靠性评估服务（三层框架）。"""

from __future__ import annotations

import json
import logging
import re

from app.constant.prompt_constant import (
    SYSTEM_PROMPT_RESEARCH_ASSISTANT,
)
from app.models.research_models import (
    ClaimReliability,
    ComparisonSummary,
    PaperInsight,
    SynthesisReliability,
)
from app.services.core.llm_service import LLMService

logger = logging.getLogger(__name__)

CLAIM_RELIABILITY_PROMPT = """
请基于以下多篇论文的洞察和比较结果，对研究综合中的每个关键结论进行证据可靠性评估。

研究主题：{topic}

论文洞察：
{insights_payload}

比较结论：
{comparison_payload}

输出 JSON 对象，字段要求：
1. claims: 数组，每项包含：
   - claim: 一个关键结论
   - supporting_papers: 支撑该结论的论文 ID 数组
   - contradicting_papers: 与该结论矛盾的论文 ID 数组（如有）
   - evidence_count: 支撑论文的数量
   - reliability_level: 取值之一：strong（多源强方法支撑）/ moderate（有支撑但方法一般）/ weak（仅弱证据）/ isolated（仅单一来源）
   - reliability_score: 0 到 1 之间的小数
   - reasoning: 判断依据
   - quality_signals: 数组，说明支撑证据的质量特征（如"3篇使用了标准benchmark"、"2篇公开了代码"等）
最多输出 6 个最重要的结论。
2. coverage_assessment: 一段话评估当前论文集合对该主题的覆盖程度
3. recommended_actions: 数组，建议如何提升结论可靠性（如"补充更多实验验证类研究"、"缺少在X数据集上的对比"等）
""".strip()


class EvidenceQualityService:
    """EvidenceQualityService 三层证据可靠性评估。"""

    def __init__(self) -> None:
        self.llm_service = LLMService()

    def assess(
        self,
        topic: str,
        insights: list[PaperInsight],
        comparison: ComparisonSummary,
    ) -> SynthesisReliability:
        """assess 执行三层可靠性评估。"""
        logger.info(
            "EvidenceQualityService.assess start, topic=%s, insight_count=%s",
            topic, len(insights),
        )

        if not insights:
            return SynthesisReliability(
                coverage_assessment="无可用论文数据。",
                recommended_actions=["请扩大检索范围。"],
            )

        # Layer 1: Paper-level quality scores are already in insights.quality_metrics
        # (populated during extraction)

        # Layer 2 & 3: Claim-level and synthesis-level via LLM
        try:
            reliability = self._assess_by_llm(topic, insights, comparison)
        except Exception as error:
            logger.warning(
                "EvidenceQualityService LLM failed, falling back to heuristic: %s", error,
            )
            reliability = self._assess_by_heuristic(insights, comparison)

        logger.info(
            "EvidenceQualityService.assess completed, claims=%d, overall=%.2f",
            len(reliability.claims), reliability.overall_score,
        )
        return reliability

    def _assess_by_llm(
        self,
        topic: str,
        insights: list[PaperInsight],
        comparison: ComparisonSummary,
    ) -> SynthesisReliability:
        """LLM 驱动的结论级可靠性评估。"""
        # Build compact payload
        insights_payload = json.dumps([
            {
                "paper_id": ins.paper.paper_id,
                "title": ins.paper.title[:100],
                "findings": ins.findings[:200],
                "method": ins.method[:150],
                "quality_score": ins.quality_metrics.overall_score if ins.quality_metrics else 0.5,
                "study_design": ins.quality_metrics.study_design if ins.quality_metrics else "unspecified",
                "reproducibility": ins.quality_metrics.reproducibility if ins.quality_metrics else "unspecified",
                "baseline_fairness": ins.quality_metrics.baseline_fairness if ins.quality_metrics else "unspecified",
            }
            for ins in insights
        ], ensure_ascii=False)

        comparison_payload = json.dumps({
            "overview": comparison.overview[:300],
            "trends": comparison.trends[:5],
            "gaps": comparison.gaps[:5],
        }, ensure_ascii=False)

        payload = self.llm_service.ask_json(
            system_prompt=SYSTEM_PROMPT_RESEARCH_ASSISTANT,
            user_prompt=CLAIM_RELIABILITY_PROMPT.format(
                topic=topic,
                insights_payload=insights_payload,
                comparison_payload=comparison_payload,
            ),
        )

        claims: list[ClaimReliability] = []
        level_counts = {"strong": 0, "moderate": 0, "weak": 0, "isolated": 0}
        for item in payload.get("claims", []):
            level = str(item.get("reliability_level", "moderate")).strip()
            if level not in level_counts:
                level = "moderate"
            level_counts[level] += 1
            claims.append(ClaimReliability(
                claim=str(item.get("claim", "")).strip(),
                supporting_papers=[str(p).strip() for p in item.get("supporting_papers", [])],
                contradicting_papers=[str(p).strip() for p in item.get("contradicting_papers", [])],
                evidence_count=int(item.get("evidence_count", 0)),
                reliability_level=level,
                reliability_score=float(item.get("reliability_score", 0.5)),
                reasoning=str(item.get("reasoning", "")).strip(),
                quality_signals=[str(s).strip() for s in item.get("quality_signals", []) if str(s).strip()],
            ))

        overall = 0.5
        if claims:
            overall = round(sum(c.reliability_score for c in claims) / len(claims), 2)

        return SynthesisReliability(
            claims=claims,
            overall_score=overall,
            strong_count=level_counts["strong"],
            moderate_count=level_counts["moderate"],
            weak_count=level_counts["weak"],
            isolated_count=level_counts["isolated"],
            coverage_assessment=str(payload.get("coverage_assessment", "")).strip(),
            recommended_actions=[str(a).strip() for a in payload.get("recommended_actions", []) if str(a).strip()],
        )

    @staticmethod
    def _assess_by_heuristic(
        insights: list[PaperInsight],
        comparison: ComparisonSummary,
    ) -> SynthesisReliability:
        """启发式降级：基于论文质量分数和比较结果自动评估。"""
        paper_ids = [ins.paper.paper_id for ins in insights]
        avg_quality = 0.5
        if insights:
            avg_quality = sum(
                ins.quality_metrics.overall_score if ins.quality_metrics else 0.5
                for ins in insights
            ) / len(insights)

        # Extract claims from comparison gaps and trends
        claims: list[ClaimReliability] = []
        all_text = " ".join(comparison.trends + comparison.gaps)
        sentences = [s.strip() for s in re.split(r"(?<=[.!?。；;])\s+", all_text) if len(s.strip()) > 10]

        for sentence in sentences[:6]:
            level = "moderate"
            score = avg_quality
            if avg_quality >= 0.7:
                level = "strong"
            elif avg_quality >= 0.5:
                level = "moderate"
            elif avg_quality >= 0.3:
                level = "weak"
            else:
                level = "isolated"
            claims.append(ClaimReliability(
                claim=sentence,
                supporting_papers=paper_ids[:3],
                contradicting_papers=[],
                evidence_count=len(paper_ids),
                reliability_level=level,
                reliability_score=round(score, 2),
                reasoning=f"启发式评估：{len(insights)} 篇论文，平均质量 {avg_quality:.2f}",
                quality_signals=[],
            ))

        level_counts = {"strong": 0, "moderate": 0, "weak": 0, "isolated": 0}
        for c in claims:
            level_counts[c.reliability_level] += 1

        return SynthesisReliability(
            claims=claims,
            overall_score=round(avg_quality, 2),
            strong_count=level_counts["strong"],
            moderate_count=level_counts["moderate"],
            weak_count=level_counts["weak"],
            isolated_count=level_counts["isolated"],
            coverage_assessment=f"启发式评估：{len(insights)} 篇论文，平均方法学质量 {avg_quality:.2f}。",
            recommended_actions=comparison.gaps[:3] if comparison.gaps else ["建议扩大检索范围以提升结论可靠性。"],
        )
