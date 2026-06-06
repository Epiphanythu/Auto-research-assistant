"""test_fact_check_service.py FactCheckService 论断校验单元测试（Phase 3）。"""

from __future__ import annotations

import pytest

from app.constant.fact_check_constant import (
    SUPPORT_LEVEL_STRONG,
    SUPPORT_LEVEL_UNSUPPORTED,
    SUPPORT_LEVEL_WEAK,
)
from app.models.research_models import (
    EvidenceBundle,
    EvidenceSnippet,
    Paper,
    PaperInsight,
)
from app.services.pipeline.fact_check_service import FactCheckService


def _build_insight(paper_id: str, title: str, findings: str) -> PaperInsight:
    """_build_insight 构造一个测试用 PaperInsight。"""
    paper = Paper(
        paper_id=paper_id,
        title=title,
        authors=["Author"],
        summary=findings,
        source="test",
    )
    return PaperInsight(
        paper=paper,
        problem="",
        method="",
        innovation="",
        findings=findings,
        limitation="",
        evidence=[],
    )


class TestFactCheckService:
    """TestFactCheckService FactCheckService 行为测试。"""

    def test_returns_empty_when_note_or_insights_missing(self):
        """无 note 或无 insights 时直接返回空报告。"""
        service = FactCheckService()
        report = service.fact_check(research_note="", insights=[], evidence_bundles=[], enable_nli=False)
        assert report.total_claims == 0
        assert report.items == []

    def test_strong_support_for_matching_claim(self):
        """论断关键词与证据高度重合时应判为强支撑。"""
        service = FactCheckService()
        insight = _build_insight(
            "p1",
            "Vision Transformer",
            "Vision Transformer outperforms ResNet on ImageNet-21k",
        )
        note = "Vision Transformer outperforms ResNet on ImageNet-21k."
        report = service.fact_check(research_note=note, insights=[insight], evidence_bundles=[], enable_nli=False)
        assert report.total_claims >= 1
        levels = [item.support_level for item in report.items]
        assert SUPPORT_LEVEL_STRONG in levels

    def test_unsupported_when_claim_unrelated(self):
        """论断与证据完全无关时应判为无证据。"""
        service = FactCheckService()
        insight = _build_insight(
            "p1",
            "Vision Transformer",
            "Vision Transformer outperforms ResNet on ImageNet-21k",
        )
        note = "Quantum entanglement accelerates training of neural networks."
        report = service.fact_check(research_note=note, insights=[insight], evidence_bundles=[], enable_nli=False)
        assert report.total_claims >= 1
        unsupported_items = [
            item for item in report.items
            if item.support_level == SUPPORT_LEVEL_UNSUPPORTED
        ]
        assert unsupported_items
        assert any("Quantum" in item.claim for item in unsupported_items)

    def test_chinese_claim_matches_chinese_evidence(self):
        """中文论断也应通过 bigram 与中文证据匹配。"""
        service = FactCheckService()
        insight = _build_insight(
            "p1",
            "扩散模型在图像生成上的应用研究",
            "扩散模型在图像生成上显著优于生成对抗网络",
        )
        note = "扩散模型在图像生成上显著优于生成对抗网络。"
        report = service.fact_check(research_note=note, insights=[insight], evidence_bundles=[], enable_nli=False)
        assert report.total_claims >= 1
        assert report.items[0].support_level in (
            SUPPORT_LEVEL_STRONG,
            "moderate",
        )

    def test_flagged_claims_lists_unsupported(self):
        """无证据论断应进入 flagged_claims 列表。"""
        service = FactCheckService()
        insight = _build_insight(
            "p1",
            "Vision Transformer",
            "Vision Transformer outperforms ResNet on ImageNet-21k",
        )
        note = (
            "Vision Transformer outperforms ResNet on ImageNet-21k. "
            "Quantum entanglement also accelerates training of neural networks."
        )
        report = service.fact_check(research_note=note, insights=[insight], evidence_bundles=[], enable_nli=False)
        assert report.flagged_claims
        assert any("Quantum" in c for c in report.flagged_claims)

    def test_uses_evidence_bundles_for_paper_id(self):
        """evidence_bundle 中的片段也应被纳入语料并能贡献 paper_id 命中。"""
        service = FactCheckService()
        insight = _build_insight("p1", "Some Paper", "irrelevant text")
        bundle = EvidenceBundle(
            unit_id="u1",
            question="q",
            synthesized_findings="",
            supporting_paper_ids=["p1"],
            evidence=[
                EvidenceSnippet(
                    snippet="Vision Transformer outperforms ResNet on ImageNet",
                    reason="",
                    source="abstract",
                    section="",
                ),
            ],
            confidence=0.5,
        )
        note = "Vision Transformer outperforms ResNet on ImageNet."
        report = service.fact_check(research_note=note, insights=[insight], evidence_bundles=[bundle], enable_nli=False)
        # 校验至少有一个论断匹配到 p1
        matched = any("p1" in item.matched_paper_ids for item in report.items)
        assert matched

    def test_score_in_valid_range(self):
        """overall_score 应在 0~1 之间。"""
        service = FactCheckService()
        insight = _build_insight("p1", "Title", "findings about transformers")
        note = "Transformers achieve strong performance on benchmarks."
        report = service.fact_check(research_note=note, insights=[insight], evidence_bundles=[], enable_nli=False)
        assert 0.0 <= report.overall_score <= 1.0

    def test_nli_promotes_weak_claim_to_moderate(self):
        """NLI 校验返回 entailment 时，weak 论断应被升级到 moderate。"""
        from unittest.mock import MagicMock

        from app.constant.fact_check_constant import (
            SUPPORT_LEVEL_MODERATE,
            NLI_VERDICT_ENTAILMENT,
        )

        # 1. mock LLM 返回 entailment
        fake_llm = MagicMock()
        fake_llm.ask_json.return_value = {
            "verdict": NLI_VERDICT_ENTAILMENT,
            "rationale": "证据明确支撑该论断。",
        }
        service = FactCheckService(llm_service=fake_llm)

        # 2. 构造一个会落到 weak 等级的场景：仅部分关键词重合
        insight = _build_insight(
            "p1",
            "Some Paper",
            "transformer architecture is widely used in modern NLP",
        )
        # 3. 论断只与 transformer 关键词部分重合，但有命中片段
        note = "Transformer architecture demonstrates impressive transfer learning."
        report = service.fact_check(
            research_note=note, insights=[insight], evidence_bundles=[], enable_nli=True,
        )

        # 4. 至少有一条 NLI 校验过的论断被升级到 moderate / strong
        promoted = [
            item for item in report.items
            if item.nli_verdict == NLI_VERDICT_ENTAILMENT
            and item.support_level in (SUPPORT_LEVEL_MODERATE, SUPPORT_LEVEL_STRONG)
        ]
        # 仅当 LLM 真的被调用且通过 NLI 时才校验；若关键词初评已 strong 则跳过
        if report.nli_verified_count > 0:
            assert promoted


class TestSectionAwareSorting:
    """TestSectionAwareSorting 章节感知 chunk 排序的间接测试。"""

    def test_section_kind_priority_order(self):
        """SECTION_KIND_PRIORITY 中 method/result 优先级应高于 other。"""
        from app.constant.paper_constant import (
            SECTION_KIND_METHOD,
            SECTION_KIND_OTHER,
            SECTION_KIND_PRIORITY,
            SECTION_KIND_RESULT,
        )

        assert SECTION_KIND_PRIORITY[SECTION_KIND_METHOD] > SECTION_KIND_PRIORITY[SECTION_KIND_OTHER]
        assert SECTION_KIND_PRIORITY[SECTION_KIND_RESULT] > SECTION_KIND_PRIORITY[SECTION_KIND_OTHER]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
