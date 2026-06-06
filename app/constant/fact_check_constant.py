"""fact_check_constant 论断校验相关常量。"""

from __future__ import annotations

# 支撑等级标签
SUPPORT_LEVEL_STRONG = "strong"
SUPPORT_LEVEL_MODERATE = "moderate"
SUPPORT_LEVEL_WEAK = "weak"
SUPPORT_LEVEL_UNSUPPORTED = "unsupported"

# 关键词重叠阈值（论断与证据语料）
SUPPORT_THRESHOLD_STRONG = 0.6
SUPPORT_THRESHOLD_MODERATE = 0.35
SUPPORT_THRESHOLD_WEAK = 0.15

# 论断切分最小长度（短句不视为论断）
CLAIM_MIN_LEN = 8
# 单次校验论断条数上限
CLAIM_MAX_PER_NOTE = 30
# 关键词最小长度（英文）
CLAIM_KEYWORD_MIN_LEN = 3

# NLI 二次校验：仅对 weak / unsupported 论断执行；为节流也设上限
NLI_VERDICT_ENTAILMENT = "entailment"
NLI_VERDICT_CONTRADICTION = "contradiction"
NLI_VERDICT_NEUTRAL = "neutral"
NLI_MAX_CLAIMS = 8
NLI_EVIDENCE_PER_CLAIM = 3
NLI_EVIDENCE_TEXT_LIMIT = 400

