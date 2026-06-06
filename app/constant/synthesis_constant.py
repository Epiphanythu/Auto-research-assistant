"""synthesis_constant 综合阶段相关常量（自适应回环阈值等）。"""

from __future__ import annotations

# 自适应回环：综合分（加权后）低于此阈值且仍存在 gap，则触发回环
ADAPTIVE_LOOP_SCORE_THRESHOLD = 0.65

# 自适应回环最大轮数（不含首轮检索）
MAX_REFINE_ROUNDS = 2

# 自适应回环置信度组合权重（必须和为 1.0）
ADAPTIVE_WEIGHT_BUNDLE_CONFIDENCE = 0.4   # evidence_bundles 平均置信度
ADAPTIVE_WEIGHT_UNIT_CONFIDENCE = 0.4     # unit_syntheses 平均置信度
ADAPTIVE_WEIGHT_PAPER_COVERAGE = 0.2      # supporting_paper_ids 覆盖论文比例

# 单次回环候选 follow-up query 上限
FOLLOW_UP_QUERY_LIMIT = 2
