"""extraction_service 单篇论文提取服务。"""

from __future__ import annotations

import logging
import re
from typing import List, Optional

from app.constant.benchmark_alias_constant import normalize_dataset_name, normalize_metric_name
from app.constant.paper_constant import (
    DEFAULT_FULL_TEXT_CONTEXT_MAX_CHUNKS,
    DEFAULT_FULL_TEXT_CONTEXT_PER_SECTION,
    DEFAULT_MAX_EVIDENCE_COUNT,
    FULL_TEXT_SOURCE_PDF,
    LONG_PAPER_CHUNK_THRESHOLD,
    LONG_PAPER_PAGE_THRESHOLD,
    LONG_PAPER_SEGMENT_MAX_CHUNKS,
    SECTION_KIND_CONCLUSION,
    SECTION_KIND_DISCUSSION,
    SECTION_KIND_EXPERIMENT,
    SECTION_KIND_METHOD,
    SECTION_KIND_OTHER,
    SECTION_KIND_PRIORITY,
    SECTION_KIND_RESULT,
)
from app.constant.prompt_constant import (
    EXTRACTION_PROMPT_TEMPLATE,
    SYSTEM_PROMPT_RESEARCH_ASSISTANT,
)
from app.models.research_models import EvidenceSnippet, FullTextChunk, FullTextDocument, Paper, PaperInsight, PaperQualityMetrics, QuantitativeResult
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
        """_extract_by_llm 使用外部大模型提取。

        长文（page_count 或 chunk 数超阈值）触发双段抽取：method 段 + results 段
        各发一次 LLM，再以 method/results 段权重合并 payload，并去重 quantitative_results。
        """
        has_full_text = bool(full_text_document and full_text_document.chunks)

        # 1. 长文双段抽取：仅在有正文且超过阈值时触发
        if has_full_text and self._is_long_paper(full_text_document):
            payload = self._extract_long_paper(paper, full_text_document)
        else:
            full_text_context = self._build_full_text_context(paper, full_text_document)
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

        # 2. 兜底：LLM 返回结构异常时尝试从备选字段抽取文本
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
        # Parse quantitative results（dataset / metric 走别名归一）
        quantitative_results = []
        for item in payload.get("quantitative_results", []):
            if isinstance(item, dict) and (item.get("dataset") or item.get("metric") or item.get("value")):
                quantitative_results.append(QuantitativeResult(
                    dataset=normalize_dataset_name(str(item.get("dataset", ""))),
                    metric=normalize_metric_name(str(item.get("metric", ""))),
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
        """_build_abstract_evidence 构造摘要级证据片段。

        证据筛选与排序逻辑：
        1. 过滤明显是开场白/通用引言的句子（含套话词，且不含数字与方法关键词）
        2. 过滤过短（<40 字符）或纯标点的句子
        3. 按信息密度（含数字、百分比、benchmark/dataset/方法名）排序，优先保留高密度句
        """
        # 1. 套话/引言开场白判定关键词（命中且无数字/方法名时丢弃）
        BANAL_PREFIXES = (
            "in recent years", "with the development of", "with the rise of",
            "recently,", "nowadays", "it is well known", "as we all know",
            "in this paper", "this paper presents", "this work proposes",
            "近年来", "随着", "众所周知",
        )
        # 2. 信息密度信号词
        SIGNAL_KEYWORDS = (
            "%", "f1", "accuracy", "bleu", "benchmark", "defects4j", "humaneval",
            "outperform", "improve", "achieve", "propose", "introduce",
            "novel", "framework", "transformer", "fine-tun", "prompt",
            "数据集", "提升", "准确率", "实验",
        )
        DIGIT_RE = re.compile(r"\d")

        # 3. 句子信息密度评分
        scored: List[tuple[float, str]] = []
        for sentence in sentences:
            s = sentence.strip()
            if len(s) < 40:
                continue
            lower = s.lower()
            is_banal = any(prefix in lower for prefix in BANAL_PREFIXES)
            has_digit = bool(DIGIT_RE.search(s))
            signal_hits = sum(1 for kw in SIGNAL_KEYWORDS if kw in lower)
            # 套话句若不含数字且无信号词则丢弃
            if is_banal and not has_digit and signal_hits == 0:
                continue
            score = signal_hits * 1.0 + (1.5 if has_digit else 0.0) - (0.5 if is_banal else 0.0)
            scored.append((score, s))

        # 4. 按分数降序，超过上限截断；若过滤后为空则降级回退到原始前 N 句保证有证据展示
        scored.sort(key=lambda item: item[0], reverse=True)
        chosen = [s for _, s in scored[:DEFAULT_MAX_EVIDENCE_COUNT]]
        if not chosen:
            chosen = [s for s in sentences[:DEFAULT_MAX_EVIDENCE_COUNT] if s.strip()]

        evidence: List[EvidenceSnippet] = []
        for sentence in chosen:
            evidence.append(
                EvidenceSnippet(
                    snippet=sentence,
                    reason="该句直接来自摘要，含可验证的方法/指标信息。",
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
        """_build_full_text_evidence 按章节优先级 + 关键词重叠抽取正文级证据片段。"""
        # 1. 按 (section_kind 优先级, 关键词重叠数) 双键排序，优先取 Method/Result/Conclusion 章节。
        ranked_chunks = self._select_section_aware_chunks(
            query=f"{paper.get_title()} {paper.get_summary()}",
            full_text_document=full_text_document,
            max_total_chunks=DEFAULT_MAX_EVIDENCE_COUNT,
            per_section_limit=DEFAULT_FULL_TEXT_CONTEXT_PER_SECTION,
        )
        logger.info(
            "ExtractionService._build_full_text_evidence ranked chunks, paper_id=%s, candidate_count=%s",
            paper.paper_id,
            len(ranked_chunks),
        )

        # 2. 把章节级 chunk 回填为带 section_kind 元信息的证据片段。
        evidence: List[EvidenceSnippet] = []
        for chunk in ranked_chunks:
            evidence.append(
                EvidenceSnippet(
                    snippet=chunk.text[:320].strip(),
                    reason=f"该片段来自 PDF 正文 [{chunk.section_kind}] 章节，可作为正文级证据。",
                    source=FULL_TEXT_SOURCE_PDF,
                    section=chunk.section,
                    section_kind=chunk.section_kind,
                    page=chunk.page,
                )
            )
        return evidence

    def _build_full_text_context(
        self,
        paper: Paper,
        full_text_document: Optional[FullTextDocument],
    ) -> str:
        """_build_full_text_context 为单篇抽取构造章节感知的正文上下文。"""
        # 1. 有正文文档时，按章节优先级挑选 chunk 并附上 section_kind 与页码标签。
        if full_text_document and full_text_document.chunks:
            ranked_chunks = self._select_section_aware_chunks(
                query=f"{paper.get_title()} {paper.get_summary()}",
                full_text_document=full_text_document,
                max_total_chunks=DEFAULT_FULL_TEXT_CONTEXT_MAX_CHUNKS,
                per_section_limit=DEFAULT_FULL_TEXT_CONTEXT_PER_SECTION,
            )
            logger.info(
                "ExtractionService._build_full_text_context selected chunks, paper_id=%s, selected_count=%s, kinds=%s",
                paper.paper_id,
                len(ranked_chunks),
                [c.section_kind for c in ranked_chunks],
            )
            return "\n".join(
                f"[kind={chunk.section_kind}; section={chunk.section}; page={chunk.page}] {chunk.text[:600].strip()}"
                for chunk in ranked_chunks
            )

        # 2. 无正文时，利用 TLDR、作者、来源等元数据构造增强上下文
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
    def _select_section_aware_chunks(
        query: str,
        full_text_document: FullTextDocument,
        max_total_chunks: int,
        per_section_limit: int,
    ) -> List[FullTextChunk]:
        """_select_section_aware_chunks 按章节优先级 + 关键词重叠挑选 chunk。"""
        # 1. 计算 query 关键词集合，用于做次级排序。
        keywords = {
            token
            for token in re.findall(r"[A-Za-z][A-Za-z0-9\-]{2,}", query.lower())
        }

        def keyword_overlap(chunk: FullTextChunk) -> int:
            chunk_kw = set(re.findall(r"[A-Za-z][A-Za-z0-9\-]{2,}", chunk.text.lower()))
            return len(keywords & chunk_kw)

        # 2. 给每个 chunk 打分：(section 优先级, 关键词重叠, 章节内倒序页码)。
        scored: List[tuple[int, int, int, FullTextChunk]] = []
        for chunk in full_text_document.chunks:
            kind_priority = SECTION_KIND_PRIORITY.get(chunk.section_kind, 0)
            overlap = keyword_overlap(chunk)
            scored.append((kind_priority, overlap, -chunk.page, chunk))
        scored.sort(reverse=True)

        # 3. 全局按总额度配额，并按章节限流避免某一章节霸占全部配额。
        per_kind_used: dict[str, int] = {}
        selected: List[FullTextChunk] = []
        selected_ids: set[int] = set()
        for _priority, _overlap, _page_neg, chunk in scored:
            if len(selected) >= max_total_chunks:
                break
            kind = chunk.section_kind or SECTION_KIND_OTHER
            if per_kind_used.get(kind, 0) >= per_section_limit:
                continue
            selected.append(chunk)
            selected_ids.add(id(chunk))
            per_kind_used[kind] = per_kind_used.get(kind, 0) + 1

        # 4. 若按章节限流后仍不足，则放开限流再补足到上限。
        if len(selected) < max_total_chunks:
            for _priority, _overlap, _page_neg, chunk in scored:
                if id(chunk) in selected_ids:
                    continue
                if len(selected) >= max_total_chunks:
                    break
                selected.append(chunk)
                selected_ids.add(id(chunk))

        return selected

    # ── 长文双段抽取 ─────────────────────────────────────────────────────

    @staticmethod
    def _is_long_paper(full_text_document: FullTextDocument) -> bool:
        """_is_long_paper 判断是否触发长文双段抽取。"""
        if full_text_document.page_count >= LONG_PAPER_PAGE_THRESHOLD:
            return True
        if len(full_text_document.chunks) >= LONG_PAPER_CHUNK_THRESHOLD:
            return True
        return False

    def _extract_long_paper(
        self,
        paper: Paper,
        full_text_document: FullTextDocument,
    ) -> dict:
        """_extract_long_paper 长文双段抽取。

        1. 切出 method 段（method/discussion）与 results 段（result/experiment/conclusion）
        2. 各发一次 LLM 抽取，分别拿回 method-focused / results-focused 两份 payload
        3. 合并：method/innovation 取 method 段；findings/limitation 取 results 段；
           quantitative_results 去重并集；其它字段优先非空
        """
        method_kinds = (SECTION_KIND_METHOD, SECTION_KIND_DISCUSSION)
        results_kinds = (SECTION_KIND_RESULT, SECTION_KIND_EXPERIMENT, SECTION_KIND_CONCLUSION)
        method_context = self._build_segment_context(paper, full_text_document, method_kinds)
        results_context = self._build_segment_context(paper, full_text_document, results_kinds)
        logger.info(
            "ExtractionService._extract_long_paper triggered, paper_id=%s, page_count=%s, chunk_count=%s",
            paper.paper_id, full_text_document.page_count, len(full_text_document.chunks),
        )
        # 1. 第一段：method-focused
        method_payload = self.llm_service.ask_json(
            system_prompt=SYSTEM_PROMPT_RESEARCH_ASSISTANT,
            user_prompt=EXTRACTION_PROMPT_TEMPLATE.format(
                title=paper.get_title(),
                summary=paper.get_summary(),
                full_text_context=method_context or "无",
            ),
        )
        # 2. 第二段：results-focused
        results_payload = self.llm_service.ask_json(
            system_prompt=SYSTEM_PROMPT_RESEARCH_ASSISTANT,
            user_prompt=EXTRACTION_PROMPT_TEMPLATE.format(
                title=paper.get_title(),
                summary=paper.get_summary(),
                full_text_context=results_context or "无",
            ),
        )
        # 3. 合并双段结果
        return self._merge_segment_payloads(method_payload, results_payload)

    def _build_segment_context(
        self,
        paper: Paper,
        full_text_document: FullTextDocument,
        target_kinds: tuple,
    ) -> str:
        """_build_segment_context 仅在指定 section_kind 集合内挑选 chunk 拼接上下文。"""
        # 1. 过滤目标 section_kind 的 chunk
        candidates = [
            chunk for chunk in full_text_document.chunks
            if chunk.section_kind in target_kinds
        ]
        if not candidates:
            return ""
        # 2. 关键词重叠次序
        keywords = {
            token for token in re.findall(
                r"[A-Za-z][A-Za-z0-9\-]{2,}",
                f"{paper.get_title()} {paper.get_summary()}".lower(),
            )
        }
        def overlap(chunk: FullTextChunk) -> int:
            chunk_kw = set(re.findall(r"[A-Za-z][A-Za-z0-9\-]{2,}", chunk.text.lower()))
            return len(keywords & chunk_kw)
        candidates.sort(key=overlap, reverse=True)
        selected = candidates[:LONG_PAPER_SEGMENT_MAX_CHUNKS]
        return "\n".join(
            f"[kind={chunk.section_kind}; section={chunk.section}; page={chunk.page}] {chunk.text[:600].strip()}"
            for chunk in selected
        )

    @staticmethod
    def _merge_segment_payloads(method_payload: dict, results_payload: dict) -> dict:
        """_merge_segment_payloads 合并 method 段与 results 段的 LLM 抽取结果。"""
        # 1. method 段优先字段：method/innovation/problem
        # 2. results 段优先字段：findings/limitation
        # 3. 其他字段（confidence/quality_metrics）优先取非空
        merged: dict = {}
        method_first_keys = ("method", "innovation", "problem")
        results_first_keys = ("findings", "limitation")
        for key in method_first_keys:
            merged[key] = method_payload.get(key) or results_payload.get(key) or ""
        for key in results_first_keys:
            merged[key] = results_payload.get(key) or method_payload.get(key) or ""
        # 4. quantitative_results 取并集（按归一化后的 dataset+metric+value 去重）
        merged_quant: list[dict] = []
        seen: set[tuple] = set()
        for item in list(method_payload.get("quantitative_results", []) or []) + list(
            results_payload.get("quantitative_results", []) or []
        ):
            if not isinstance(item, dict):
                continue
            ds = normalize_dataset_name(str(item.get("dataset", "")))
            mt = normalize_metric_name(str(item.get("metric", "")))
            val = str(item.get("value", "")).strip()
            key = (ds, mt, val)
            if not any(key) or key in seen:
                continue
            seen.add(key)
            normalized_item = {**item, "dataset": ds, "metric": mt}
            merged_quant.append(normalized_item)
        merged["quantitative_results"] = merged_quant
        # 5. quality_metrics 优先 method 段（更倾向于方法学评估）
        merged["quality_metrics"] = (
            method_payload.get("quality_metrics") or results_payload.get("quality_metrics")
        )
        # 6. confidence 取两段平均（缺省回退 0.7）
        method_conf = float(method_payload.get("confidence", 0.7) or 0.7)
        results_conf = float(results_payload.get("confidence", 0.7) or 0.7)
        merged["confidence"] = round((method_conf + results_conf) / 2, 2)
        return merged
