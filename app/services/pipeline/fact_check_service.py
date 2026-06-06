"""fact_check_service 论断级事实校验服务（Phase 3 + Phase 4 NLI 升级）。

将 research_note 按句子切分后，逐条与已抽取证据进行关键词匹配，标记
"无证据/弱证据/中等支撑/强支撑" 四级；对其中 weak / unsupported 论断
再调用 LLM 做一次轻量 NLI（蕴含 / 反驳 / 中立）二次确认，避免简单
关键词匹配把否定/转折句误判。
"""

from __future__ import annotations

import json
import logging
import re
from typing import List, Optional

from app.constant.fact_check_constant import (
    CLAIM_KEYWORD_MIN_LEN,
    CLAIM_MAX_PER_NOTE,
    CLAIM_MIN_LEN,
    NLI_EVIDENCE_PER_CLAIM,
    NLI_EVIDENCE_TEXT_LIMIT,
    NLI_MAX_CLAIMS,
    NLI_VERDICT_CONTRADICTION,
    NLI_VERDICT_ENTAILMENT,
    NLI_VERDICT_NEUTRAL,
    SUPPORT_LEVEL_MODERATE,
    SUPPORT_LEVEL_STRONG,
    SUPPORT_LEVEL_UNSUPPORTED,
    SUPPORT_LEVEL_WEAK,
    SUPPORT_THRESHOLD_MODERATE,
    SUPPORT_THRESHOLD_STRONG,
    SUPPORT_THRESHOLD_WEAK,
)
from app.constant.prompt_constant import (
    FACT_CHECK_NLI_PROMPT_TEMPLATE,
    SYSTEM_PROMPT_RESEARCH_ASSISTANT,
)
from app.models.research_models import (
    ClaimFactCheck,
    EvidenceBundle,
    EvidenceSnippet,
    FactCheckReport,
    PaperInsight,
)
from app.services.core.llm_service import LLMService

logger = logging.getLogger(__name__)


# 句子切分：中英混合标点
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？!?；;])|(?<=\.)\s+")
# 英文关键词（≥3 字符的字母数字串）
_EN_KEYWORD_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9\-]{2,}")
# 中文字符
_CN_CHAR_RE = re.compile(r"[一-鿿]")


class FactCheckService:
    """FactCheckService 对 research_note 中的论断做证据反查。"""

    def __init__(self, llm_service: Optional[LLMService] = None) -> None:
        # 1. NLI 校验需要 LLM；调用方可注入或服务内自建
        self._llm_service = llm_service

    def fact_check(
        self,
        research_note: str,
        insights: List[PaperInsight],
        evidence_bundles: List[EvidenceBundle],
        enable_nli: bool = True,
    ) -> FactCheckReport:
        """fact_check 把 research_note 按句切分，逐条反查证据匹配度。"""
        # 1. 没有 note 或没有任何证据时直接返回空报告，避免误判
        if not research_note or not insights:
            return FactCheckReport()

        claims = self._split_claims(research_note)
        if not claims:
            return FactCheckReport()

        # 2. 预构建证据语料（合并 insights.evidence + bundle.evidence + insight 文本字段）
        evidence_corpus = self._build_evidence_corpus(insights, evidence_bundles)

        # 3. 关键词级初评
        items: List[ClaimFactCheck] = [
            self._check_single_claim(claim, evidence_corpus)
            for claim in claims
        ]

        # 4. 对 weak / unsupported 的论断，调用 LLM 做 NLI 二次确认（最多 NLI_MAX_CLAIMS 条）
        nli_verified = 0
        if enable_nli:
            nli_verified = self._refine_with_nli(items)

        # 5. 汇总统计
        supported_count = 0
        weak_count = 0
        unsupported_count = 0
        flagged: List[str] = []
        for item in items:
            if item.support_level in (SUPPORT_LEVEL_STRONG, SUPPORT_LEVEL_MODERATE):
                supported_count += 1
            elif item.support_level == SUPPORT_LEVEL_WEAK:
                weak_count += 1
            else:
                unsupported_count += 1
                flagged.append(item.claim)

        total = len(items)
        overall_score = round(supported_count / total, 2) if total else 0.0
        return FactCheckReport(
            total_claims=total,
            supported_count=supported_count,
            weak_count=weak_count,
            unsupported_count=unsupported_count,
            overall_score=overall_score,
            items=items,
            flagged_claims=flagged,
            nli_verified_count=nli_verified,
        )

    def _split_claims(self, research_note: str) -> List[str]:
        """_split_claims 将 research_note 按中英文标点切分为论断句列表。"""
        # 1. 拆分并归一化
        raw_sentences = _SENTENCE_SPLIT_RE.split(research_note)
        claims: List[str] = []
        for sent in raw_sentences:
            cleaned = sent.strip()
            if len(cleaned) < CLAIM_MIN_LEN:
                continue
            claims.append(cleaned)
        # 2. 限制条数避免开销膨胀
        return claims[:CLAIM_MAX_PER_NOTE]

    def _build_evidence_corpus(
        self,
        insights: List[PaperInsight],
        evidence_bundles: List[EvidenceBundle],
    ) -> List[tuple[str, str, EvidenceSnippet | None]]:
        """_build_evidence_corpus 构造 (paper_id, text, evidence_snippet) 三元组列表。"""
        corpus: List[tuple[str, str, EvidenceSnippet | None]] = []
        # 1. insights 自身的结构化字段（findings / method / problem / innovation）
        for ins in insights:
            paper_id = ins.paper.paper_id
            base_text = " ".join([
                ins.paper.title or "",
                ins.paper.summary or "",
                ins.problem or "",
                ins.method or "",
                ins.innovation or "",
                ins.findings or "",
                ins.limitation or "",
            ])
            corpus.append((paper_id, base_text, None))
            # 1.1 insight 自带的证据片段
            for ev in ins.evidence:
                corpus.append((paper_id, ev.snippet, ev))
        # 2. evidence_bundles 中的证据片段（与 unit 关联但 paper_id 已在 supporting_paper_ids 中）
        paper_ids_in_insights = {ins.paper.paper_id for ins in insights}
        for bundle in evidence_bundles:
            fallback_paper_id = (
                bundle.supporting_paper_ids[0]
                if bundle.supporting_paper_ids else ""
            )
            for ev in bundle.evidence:
                # 仅在该证据 paper 仍在 insights 中时纳入，避免幻引用
                if fallback_paper_id and fallback_paper_id in paper_ids_in_insights:
                    corpus.append((fallback_paper_id, ev.snippet, ev))
        return corpus

    def _check_single_claim(
        self,
        claim: str,
        evidence_corpus: List[tuple[str, str, EvidenceSnippet | None]],
    ) -> ClaimFactCheck:
        """_check_single_claim 单条论断的关键词匹配评估。"""
        # 1. 抽取论断的关键词集合（英文 + 中文 bigram）
        claim_en, claim_cn = self._extract_keywords(claim)
        if not claim_en and not claim_cn:
            return ClaimFactCheck(
                claim=claim,
                supported=False,
                support_level=SUPPORT_LEVEL_UNSUPPORTED,
                reason="未能从论断中抽取出有效关键词",
            )

        # 2. 与证据语料逐条计算重叠分，记录最匹配的证据
        best_score = 0.0
        matched_paper_ids: List[str] = []
        matched_evidence: List[EvidenceSnippet] = []
        for paper_id, text, snippet in evidence_corpus:
            text_en, text_cn = self._extract_keywords(text)
            score = self._overlap_score(claim_en, claim_cn, text_en, text_cn)
            if score >= SUPPORT_THRESHOLD_WEAK:
                if paper_id and paper_id not in matched_paper_ids:
                    matched_paper_ids.append(paper_id)
                if snippet is not None and len(matched_evidence) < 3:
                    matched_evidence.append(snippet)
            if score > best_score:
                best_score = score

        # 3. 根据阈值映射到 support_level
        if best_score >= SUPPORT_THRESHOLD_STRONG:
            level = SUPPORT_LEVEL_STRONG
            reason = f"关键词重叠分 {best_score:.2f}，多处证据支撑"
        elif best_score >= SUPPORT_THRESHOLD_MODERATE:
            level = SUPPORT_LEVEL_MODERATE
            reason = f"关键词重叠分 {best_score:.2f}，存在中等强度证据"
        elif best_score >= SUPPORT_THRESHOLD_WEAK:
            level = SUPPORT_LEVEL_WEAK
            reason = f"关键词重叠分 {best_score:.2f}，证据较弱"
        else:
            level = SUPPORT_LEVEL_UNSUPPORTED
            reason = f"关键词重叠分 {best_score:.2f}，未在已抽取证据中找到对应支撑"

        return ClaimFactCheck(
            claim=claim,
            supported=level in (SUPPORT_LEVEL_STRONG, SUPPORT_LEVEL_MODERATE),
            support_level=level,
            matched_paper_ids=matched_paper_ids[:5],
            matched_evidence=matched_evidence,
            keyword_overlap_score=round(best_score, 3),
            reason=reason,
        )

    def _extract_keywords(self, text: str) -> tuple[set[str], set[str]]:
        """_extract_keywords 抽取英文关键词集合 + 中文 bigram 集合。"""
        if not text:
            return set(), set()
        lower = text.lower()
        en_set = {
            w for w in _EN_KEYWORD_RE.findall(lower)
            if len(w) >= CLAIM_KEYWORD_MIN_LEN
        }
        cn_chars = _CN_CHAR_RE.findall(text)
        cn_bigrams = {
            cn_chars[i] + cn_chars[i + 1]
            for i in range(len(cn_chars) - 1)
        }
        return en_set, cn_bigrams

    def _overlap_score(
        self,
        claim_en: set[str],
        claim_cn: set[str],
        text_en: set[str],
        text_cn: set[str],
    ) -> float:
        """_overlap_score 计算论断 vs 证据的归一化重叠分（0~1）。"""
        # 1. 英文部分：按论断关键词覆盖率
        en_score = 0.0
        if claim_en:
            en_score = len(claim_en & text_en) / len(claim_en)
        # 2. 中文部分：按论断 bigram 覆盖率
        cn_score = 0.0
        if claim_cn:
            cn_score = len(claim_cn & text_cn) / len(claim_cn)
        # 3. 合并：取较大者，确保中英任一充分匹配即可
        return max(en_score, cn_score)

    # ── NLI 二次校验 ──────────────────────────────────────────────────────────

    def _refine_with_nli(self, items: List[ClaimFactCheck]) -> int:
        """_refine_with_nli 对 weak / unsupported 论断做 LLM NLI 校验，更新 support_level。

        判定规则：
        - entailment：升级到 moderate（避免与 strong 判错）；
        - contradiction：保持 unsupported 并加注矛盾；
        - neutral：保持原判（默认）。
        """
        # 1. 选出需要 NLI 的候选论断（weak / unsupported 且有 matched_evidence 或 matched_paper_ids）
        candidates: List[ClaimFactCheck] = []
        for item in items:
            if item.support_level not in (SUPPORT_LEVEL_WEAK, SUPPORT_LEVEL_UNSUPPORTED):
                continue
            if not item.matched_evidence and not item.matched_paper_ids:
                # 完全无证据匹配的论断不送 LLM，节流
                continue
            candidates.append(item)
            if len(candidates) >= NLI_MAX_CLAIMS:
                break
        if not candidates:
            return 0

        # 2. 调用 LLM 逐条校验；失败则跳过该条
        llm_service = self._llm_service or LLMService()
        verified = 0
        for item in candidates:
            verdict, rationale = self._nli_check_single(llm_service, item)
            if verdict is None:
                continue
            verified += 1
            item.nli_verdict = verdict
            item.nli_rationale = rationale
            self._apply_nli_to_item(item, verdict)
        return verified

    def _apply_nli_to_item(self, item: ClaimFactCheck, verdict: str) -> None:
        """_apply_nli_to_item 根据 NLI verdict 调整 support_level / supported / reason。"""
        if verdict == NLI_VERDICT_ENTAILMENT:
            # 1. 蕴含：升至 moderate（仅信任 NLI 升一档，不直升 strong）
            item.support_level = SUPPORT_LEVEL_MODERATE
            item.supported = True
            item.reason = (
                f"{item.reason}；NLI 校验：证据蕴含该论断"
            )
        elif verdict == NLI_VERDICT_CONTRADICTION:
            # 2. 矛盾：保留 unsupported，并显式标记矛盾
            item.support_level = SUPPORT_LEVEL_UNSUPPORTED
            item.supported = False
            item.reason = (
                f"{item.reason}；NLI 校验：证据与该论断存在矛盾"
            )
        else:
            # 3. 中立：保持原判，仅追加说明
            item.reason = f"{item.reason}；NLI 校验：证据与论断无直接关系"

    def _nli_check_single(
        self,
        llm_service: LLMService,
        item: ClaimFactCheck,
    ) -> tuple[Optional[str], str]:
        """_nli_check_single 单条论断的 NLI 调用，返回 (verdict, rationale)。"""
        # 1. 拼装证据 payload：截断每条文本以控制 token
        evidence_texts: List[str] = []
        for ev in item.matched_evidence[:NLI_EVIDENCE_PER_CLAIM]:
            snippet = (ev.snippet or "").strip()
            if snippet:
                evidence_texts.append(snippet[:NLI_EVIDENCE_TEXT_LIMIT])
        if not evidence_texts and item.matched_paper_ids:
            # 没有具体证据片段时退化为 paper_id 列表说明
            evidence_texts.append(
                "相关候选论文：" + ", ".join(item.matched_paper_ids[:5])
            )
        if not evidence_texts:
            return None, ""

        evidence_payload = json.dumps(evidence_texts, ensure_ascii=False)

        # 2. 调用 LLM；任何异常都不阻塞整体 fact_check 流程
        try:
            payload = llm_service.ask_json(
                system_prompt=SYSTEM_PROMPT_RESEARCH_ASSISTANT,
                user_prompt=FACT_CHECK_NLI_PROMPT_TEMPLATE.format(
                    claim=item.claim,
                    evidence_payload=evidence_payload,
                ),
            )
        except Exception as error:  # noqa: BLE001 — NLI 失败不应中断 fact_check
            logger.warning(
                "FactCheckService._nli_check_single failed claim=%s, error=%s",
                item.claim[:40], error,
            )
            return None, ""

        # 3. 校验 verdict 合法性
        verdict_raw = str(payload.get("verdict", "")).strip().lower()
        rationale = str(payload.get("rationale", "")).strip()
        if verdict_raw not in (
            NLI_VERDICT_ENTAILMENT,
            NLI_VERDICT_CONTRADICTION,
            NLI_VERDICT_NEUTRAL,
        ):
            return None, ""
        return verdict_raw, rationale
