"""extraction_service 单篇论文提取服务。"""

from __future__ import annotations

import logging
import re
from typing import List, Optional

from app.constant.paper_constant import DEFAULT_MAX_EVIDENCE_COUNT, FULL_TEXT_SOURCE_PDF
from app.constant.prompt_constant import (
    EXTRACTION_PROMPT_TEMPLATE,
    SYSTEM_PROMPT_RESEARCH_ASSISTANT,
)
from app.models.research_models import EvidenceSnippet, FullTextDocument, Paper, PaperInsight, PaperQualityMetrics, QuantitativeResult
from app.services.core.llm_service import LLMService

logger = logging.getLogger(__name__)


class ExtractionService:
    """ExtractionService 单篇论文结构化提取器。"""

    def __init__(self) -> None:
        self.llm_service = LLMService()

    def extract(
        self,
        paper: Paper,
        full_text_document: Optional[FullTextDocument] = None,
    ) -> PaperInsight:
        """extract 提取单篇论文洞察。"""
        # 1. 强制使用外部大模型完成核心语义提取，并优先消费正文片段。
        logger.info(
            "ExtractionService.extract start, paper_id=%s, has_full_text=%s",
            paper.paper_id,
            bool(full_text_document and full_text_document.chunks),
        )
        llm_insight = self._extract_by_llm(paper, full_text_document)

        # 2. 若存在全文文档，则优先构造正文级证据片段，否则回退到摘要证据。
        if full_text_document and full_text_document.chunks:
            evidence = self._build_full_text_evidence(
                paper,
                full_text_document,
            )
            llm_insight.full_text_used = bool(evidence)
            logger.info(
                "ExtractionService.extract use full text evidence, paper_id=%s, evidence_count=%s",
                paper.paper_id,
                len(evidence),
            )
        else:
            sentences = self._split_sentences(paper.get_summary())
            evidence = self._build_abstract_evidence(sentences)
            logger.info(
                "ExtractionService.extract fallback to abstract evidence, paper_id=%s, evidence_count=%s",
                paper.paper_id,
                len(evidence),
            )
        llm_insight.evidence = evidence
        llm_insight.confidence = self._calculate_confidence(
            llm_insight.problem,
            llm_insight.method,
            llm_insight.innovation,
            llm_insight.findings,
            llm_insight.limitation,
        )
        logger.info(
            "ExtractionService.extract completed, paper_id=%s, confidence=%s, full_text_used=%s",
            paper.paper_id,
            llm_insight.confidence,
            llm_insight.full_text_used,
        )
        return llm_insight

    def _extract_by_llm(
        self,
        paper: Paper,
        full_text_document: Optional[FullTextDocument] = None,
    ) -> PaperInsight:
        """_extract_by_llm 使用外部大模型提取。"""
        has_full_text = bool(full_text_document and full_text_document.chunks)
        full_text_context = self._build_full_text_context(
            paper,
            full_text_document,
        )
        logger.info(
            "ExtractionService._extract_by_llm request prepared, paper_id=%s, context_length=%s, has_full_text=%s",
            paper.paper_id,
            len(full_text_context),
            has_full_text,
        )
        payload = self.llm_service.ask_json(
            system_prompt=SYSTEM_PROMPT_RESEARCH_ASSISTANT,
            user_prompt=EXTRACTION_PROMPT_TEMPLATE.format(
                title=paper.get_title(),
                summary=paper.get_summary(),
                full_text_context=full_text_context or "无",
            ),
        )

        # If LLM returned unexpected structure, extract text from any available field
        fallback_text = ""
        if not payload.get("method") and not payload.get("findings"):
            for key in ("answer", "summary", "response", "content", "description"):
                if payload.get(key):
                    fallback_text = str(payload[key])
                    break
            if fallback_text:
                payload["findings"] = fallback_text
                payload["method"] = fallback_text[:200]

        # If still empty, use paper abstract as fallback
        if not payload.get("findings"):
            abstract = paper.get_summary()
            if abstract:
                payload["findings"] = abstract[:400]
                payload["problem"] = abstract[:200]

        logger.info(
            "ExtractionService._extract_by_llm response received, paper_id=%s, fields=%s",
            paper.paper_id,
            [key for key in ["problem", "method", "innovation", "findings", "limitation"] if payload.get(key)],
        )
        # Parse quantitative results
        quantitative_results = []
        for item in payload.get("quantitative_results", []):
            if isinstance(item, dict) and (item.get("dataset") or item.get("metric") or item.get("value")):
                quantitative_results.append(QuantitativeResult(
                    dataset=str(item.get("dataset", "")).strip(),
                    metric=str(item.get("metric", "")).strip(),
                    value=str(item.get("value", "")).strip(),
                    baseline=str(item.get("baseline", "")).strip(),
                ))

        # Parse quality metrics
        quality_metrics = None
        qm = payload.get("quality_metrics")
        if isinstance(qm, dict):
            design = str(qm.get("study_design", "unspecified")).strip()
            valid_designs = {"controlled_experiment", "ablation", "observational", "theoretical", "benchmark", "survey", "unspecified"}
            data_avail = str(qm.get("data_availability", "unspecified")).strip()
            valid_data = {"public", "private", "synthetic", "unspecified"}
            repro = str(qm.get("reproducibility", "unspecified")).strip()
            valid_repro = {"code_public", "code_partial", "code_unavailable", "unspecified"}
            baseline_f = str(qm.get("baseline_fairness", "unspecified")).strip()
            valid_bf = {"standard_baselines", "weak_baselines", "no_comparison", "unspecified"}
            metric_t = str(qm.get("metric_type", "unspecified")).strip()
            valid_mt = {"standard", "custom", "mixed", "unspecified"}
            # Calculate composite score
            score = 0.2
            if design in {"controlled_experiment", "benchmark"}:
                score += 0.25
            elif design in {"ablation", "observational"}:
                score += 0.15
            if data_avail == "public":
                score += 0.15
            if repro == "code_public":
                score += 0.15
            elif repro == "code_partial":
                score += 0.08
            if baseline_f == "standard_baselines":
                score += 0.15
            elif baseline_f == "weak_baselines":
                score += 0.05
            if metric_t == "standard":
                score += 0.1
            quality_metrics = PaperQualityMetrics(
                study_design=design if design in valid_designs else "unspecified",
                data_availability=data_avail if data_avail in valid_data else "unspecified",
                reproducibility=repro if repro in valid_repro else "unspecified",
                baseline_fairness=baseline_f if baseline_f in valid_bf else "unspecified",
                metric_type=metric_t if metric_t in valid_mt else "unspecified",
                overall_score=round(min(score, 1.0), 2),
                note=str(qm.get("note", "")).strip(),
            )

        return PaperInsight(
            paper=paper,
            problem=str(payload.get("problem", "")),
            method=str(payload.get("method", "")),
            innovation=str(payload.get("innovation", "")),
            findings=str(payload.get("findings", "")),
            limitation=str(payload.get("limitation", "")),
            evidence=[],
            confidence=float(payload.get("confidence", 0.7)),
            full_text_used=has_full_text,
            quantitative_results=quantitative_results,
            quality_metrics=quality_metrics,
        )

    @staticmethod
    def _split_sentences(text: str) -> List[str]:
        """_split_sentences 切分句子。"""
        chunks = re.split(r"(?<=[.!?。；;])\s+", text.strip())
        return [chunk.strip() for chunk in chunks if chunk.strip()]

    @staticmethod
    def _build_abstract_evidence(sentences: List[str]) -> List[EvidenceSnippet]:
        """_build_abstract_evidence 构造摘要级证据片段。"""
        evidence: List[EvidenceSnippet] = []
        for sentence in sentences[:DEFAULT_MAX_EVIDENCE_COUNT]:
            evidence.append(
                EvidenceSnippet(
                    snippet=sentence,
                    reason="该句直接来自摘要，可作为研究结论的证据来源。",
                )
            )
        return evidence

    @staticmethod
    def _calculate_confidence(
        problem: str,
        method: str,
        innovation: str,
        findings: str,
        limitation: str,
    ) -> float:
        """_calculate_confidence 根据字段完整度计算置信度。"""
        non_empty_count = sum(
            1
            for item in [problem, method, innovation, findings, limitation]
            if item and item.strip()
        )
        return round(0.3 + non_empty_count * 0.14, 2)

    def _build_full_text_evidence(
        self,
        paper: Paper,
        full_text_document: FullTextDocument,
    ) -> List[EvidenceSnippet]:
        """_build_full_text_evidence 构造正文级证据片段。"""
        # 1. 按标题和摘要关键词筛出更相关的正文 chunk。
        ranked_chunks = self._rank_chunks(
            query=f"{paper.get_title()} {paper.get_summary()}",
            full_text_document=full_text_document,
        )
        logger.info(
            "ExtractionService._build_full_text_evidence ranked chunks, paper_id=%s, candidate_count=%s",
            paper.paper_id,
            len(ranked_chunks),
        )

        # 2. 将正文 chunk 回填为可追溯的证据片段，并保留 page/section 元信息。
        evidence: List[EvidenceSnippet] = []
        for chunk in ranked_chunks[:DEFAULT_MAX_EVIDENCE_COUNT]:
            evidence.append(
                EvidenceSnippet(
                    snippet=chunk.text[:320].strip(),
                    reason="该片段来自 PDF 正文，可作为正文级证据。",
                    source=FULL_TEXT_SOURCE_PDF,
                    section=chunk.section,
                    page=chunk.page,
                )
            )
        return evidence

    def _build_full_text_context(
        self,
        paper: Paper,
        full_text_document: Optional[FullTextDocument],
    ) -> str:
        """_build_full_text_context 为单篇提取构造正文上下文。"""
        if full_text_document and full_text_document.chunks:
            ranked_chunks = self._rank_chunks(
                query=f"{paper.get_title()} {paper.get_summary()}",
                full_text_document=full_text_document,
            )
            logger.info(
                "ExtractionService._build_full_text_context selected chunks, paper_id=%s, selected_count=%s",
                paper.paper_id,
                min(len(ranked_chunks), DEFAULT_MAX_EVIDENCE_COUNT),
            )
            return "\n".join(
                f"[page={chunk.page}; section={chunk.section}] {chunk.text[:500].strip()}"
                for chunk in ranked_chunks[:DEFAULT_MAX_EVIDENCE_COUNT]
            )

        # 无全文时，利用 TLDR、作者、来源等元数据构造增强上下文
        context_parts: list[str] = []
        if paper.tldr:
            context_parts.append(f"[TLDR] {paper.tldr.strip()}")
        if paper.authors:
            context_parts.append(f"[作者] {', '.join(paper.authors[:5])}")
        if paper.published:
            context_parts.append(f"[发表日期] {paper.published}")
        if paper.citation_count:
            context_parts.append(f"[被引次数] {paper.citation_count}")
        if paper.doi:
            context_parts.append(f"[DOI] {paper.doi}")
        if context_parts:
            logger.info(
                "ExtractionService._build_full_text_context enriched abstract, paper_id=%s, parts=%d",
                paper.paper_id,
                len(context_parts),
            )
            return "\n".join(context_parts)

        logger.info(
            "ExtractionService._build_full_text_context no enrichment, paper_id=%s",
            paper.paper_id,
        )
        return ""

    @staticmethod
    def _rank_chunks(query: str, full_text_document: FullTextDocument):
        """_rank_chunks 根据关键词重叠度排序正文 chunk。"""
        keywords = {
            token
            for token in re.findall(r"[A-Za-z][A-Za-z0-9\-]{2,}", query.lower())
        }

        def score(chunk) -> tuple[int, int]:
            chunk_keywords = set(
                re.findall(r"[A-Za-z][A-Za-z0-9\-]{2,}", chunk.text.lower())
            )
            overlap = len(keywords & chunk_keywords)
            return overlap, -chunk.page

        return sorted(
            full_text_document.chunks,
            key=score,
            reverse=True,
        )
