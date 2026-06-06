"""benchmark_alias_constant 数据集与指标别名标准化字典。

用于在 quantitative_results 等聚合场景将常见数据集 / 评测指标的多种写法
归一到同一个标准名称，避免 "GSM8K"、"GSM-8K"、"GSM_8K" 三条数据被当成不同
基准重复列出。
"""

from __future__ import annotations

# 数据集别名 -> 标准名（key 全部小写、去除分隔符）
DATASET_ALIAS_MAP: dict[str, str] = {
    # 数学推理
    "gsm8k": "GSM8K",
    "gsm 8k": "GSM8K",
    "math": "MATH",
    "mathqa": "MathQA",
    "mathqa python": "MathQA-Python",
    # 代码 / 程序修复
    "humaneval": "HumanEval",
    "humaneval+": "HumanEval+",
    "humanevalplus": "HumanEval+",
    "mbpp": "MBPP",
    "mbpp+": "MBPP+",
    "mbppplus": "MBPP+",
    "apps": "APPS",
    "codecontests": "CodeContests",
    "code contests": "CodeContests",
    "swe bench": "SWE-bench",
    "swebench": "SWE-bench",
    "defects4j": "Defects4J",
    "quixbugs": "QuixBugs",
    "bugsinpy": "BugsInPy",
    # 通用问答 / 知识
    "mmlu": "MMLU",
    "mmlu pro": "MMLU-Pro",
    "bbh": "BIG-Bench Hard",
    "big bench hard": "BIG-Bench Hard",
    "arc": "ARC",
    "hellaswag": "HellaSwag",
    "truthfulqa": "TruthfulQA",
    "naturalquestions": "Natural Questions",
    "natural questions": "Natural Questions",
    "triviaqa": "TriviaQA",
    "squad": "SQuAD",
    "squad2": "SQuAD 2.0",
    "boolq": "BoolQ",
    # 摘要 / 阅读理解
    "cnn dailymail": "CNN/DailyMail",
    "cnn/dailymail": "CNN/DailyMail",
    "xsum": "XSum",
    "samsum": "SAMSum",
    # 翻译
    "wmt14": "WMT14",
    "wmt16": "WMT16",
    "wmt19": "WMT19",
    "wmt22": "WMT22",
    # 多模态
    "vqa": "VQA",
    "vqav2": "VQA v2",
    "okvqa": "OK-VQA",
    "coco": "COCO",
    "imagenet": "ImageNet",
    # Agent / 工具
    "toolbench": "ToolBench",
    "agentbench": "AgentBench",
    "webarena": "WebArena",
}

# 指标别名 -> 标准名（key 全部小写、去除分隔符）
METRIC_ALIAS_MAP: dict[str, str] = {
    # 准确率系
    "accuracy": "accuracy",
    "acc": "accuracy",
    "exact match": "exact_match",
    "em": "exact_match",
    "exact match score": "exact_match",
    "pass@1": "pass@1",
    "pass at 1": "pass@1",
    "pass@10": "pass@10",
    "pass@100": "pass@100",
    "resolve@1": "resolve@1",
    "resolve rate": "resolve@1",
    # F1 系
    "f1": "f1",
    "f1 score": "f1",
    "macro f1": "macro_f1",
    "micro f1": "micro_f1",
    # 摘要系
    "rouge 1": "rouge-1",
    "rouge1": "rouge-1",
    "rouge 2": "rouge-2",
    "rouge2": "rouge-2",
    "rouge l": "rouge-l",
    "rougel": "rouge-l",
    # 翻译系
    "bleu": "BLEU",
    "bleu 4": "BLEU-4",
    "chrf": "chrF",
    "chrf++": "chrF++",
    "ter": "TER",
    "comet": "COMET",
    # 检索 / 推荐
    "ndcg": "nDCG",
    "ndcg@10": "nDCG@10",
    "mrr": "MRR",
    "recall@1": "recall@1",
    "recall@10": "recall@10",
    "hit@1": "hit@1",
    "hit@10": "hit@10",
    # 困惑度
    "perplexity": "perplexity",
    "ppl": "perplexity",
}


def normalize_dataset_name(raw: str) -> str:
    """normalize_dataset_name 将数据集名称规整为标准写法，未匹配时去多余分隔符回退。"""
    if not raw:
        return ""
    key = _normalize_key(raw)
    if key in DATASET_ALIAS_MAP:
        return DATASET_ALIAS_MAP[key]
    return raw.strip()


def normalize_metric_name(raw: str) -> str:
    """normalize_metric_name 将指标名称规整为标准写法，未匹配时去多余分隔符回退。"""
    if not raw:
        return ""
    key = _normalize_key(raw)
    if key in METRIC_ALIAS_MAP:
        return METRIC_ALIAS_MAP[key]
    return raw.strip()


def _normalize_key(raw: str) -> str:
    """_normalize_key 生成查表用归一化 key（小写、连字符/下划线变空格、压缩多空格）。"""
    text = raw.strip().lower()
    for ch in ("_", "-", "/", "\\"):
        text = text.replace(ch, " ")
    while "  " in text:
        text = text.replace("  ", " ")
    return text.strip()
