"""structured_logging 结构化 JSON 日志 + LLM 调用统计。"""

from __future__ import annotations

import json
import logging
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


def emit_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    """emit_event 以 JSON 形式发出一条结构化日志。

    日志正文是单行 JSON，便于 grep / 日志平台解析；
    同时保留 logger.info 接口，普通文本查看器也能读。
    """
    payload: Dict[str, Any] = {"event": event, "ts": time.time()}
    for key, value in fields.items():
        if value is None:
            continue
        payload[key] = value
    try:
        logger.info(json.dumps(payload, ensure_ascii=False, default=str))
    except (TypeError, ValueError):
        # 兜底：value 不可序列化时打印原文
        logger.info("event=%s fields=%s", event, fields)


@dataclass
class LLMCallStats:
    """LLMCallStats 单次研究任务期间累计的 LLM 调用统计。"""

    call_count: int = 0
    cache_hit_count: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_elapsed_ms: int = 0

    def add_call(
        self,
        *,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        elapsed_ms: int = 0,
        cache_hit: bool = False,
    ) -> None:
        """add_call 累加一次调用的统计。"""
        self.call_count += 1
        if cache_hit:
            self.cache_hit_count += 1
            return
        self.prompt_tokens += max(0, prompt_tokens)
        self.completion_tokens += max(0, completion_tokens)
        self.total_elapsed_ms += max(0, elapsed_ms)

    def total_tokens(self) -> int:
        """total_tokens 合计 token。"""
        return self.prompt_tokens + self.completion_tokens

    def to_dict(self) -> Dict[str, Any]:
        """to_dict 序列化为可放入 SSE / 报告的字典。"""
        return {
            "call_count": self.call_count,
            "cache_hit_count": self.cache_hit_count,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens(),
            "total_elapsed_ms": self.total_elapsed_ms,
        }


@dataclass
class _StatsHolder:
    """_StatsHolder 线程局部统计持有者。"""

    stack: list = field(default_factory=list)


_stats_local = threading.local()


def _get_holder() -> _StatsHolder:
    """_get_holder 获取当前线程的 stats 栈。"""
    holder = getattr(_stats_local, "holder", None)
    if holder is None:
        holder = _StatsHolder()
        _stats_local.holder = holder
    return holder


def get_current_stats() -> Optional[LLMCallStats]:
    """get_current_stats 取当前作用域的 LLM 统计对象（无则返回 None）。"""
    stack = _get_holder().stack
    return stack[-1] if stack else None


@contextmanager
def llm_stats_scope(stats: Optional[LLMCallStats] = None):
    """llm_stats_scope 进入一个 LLM 统计作用域，作用域内的 LLM 调用都会记到此 stats。"""
    if stats is None:
        stats = LLMCallStats()
    holder = _get_holder()
    holder.stack.append(stats)
    try:
        yield stats
    finally:
        holder.stack.pop()
