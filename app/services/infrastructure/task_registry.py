"""task_registry 研究任务注册表。

提供刷新可恢复的 SSE 体验：任务在后台线程异步执行，所有 SSE 事件被
追加到任务的事件历史中；前端断流后通过 task_id 续连，从指定游标
继续读取后续事件，从而避免"刷新就丢进度"。
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, Iterator, List, Optional

from app.models.research_models import ResearchRequest, SSEEvent

logger = logging.getLogger(__name__)

# 任务最长保留时间（秒）：6 小时
DEFAULT_TASK_TTL_SECONDS = 6 * 60 * 60
# 单进程最多并发任务数（防止内存爆炸）
DEFAULT_MAX_TASKS = 100


@dataclass
class ResearchTask:
    """ResearchTask 单个研究任务的运行态。"""

    task_id: str
    topic: str
    request: ResearchRequest
    status: str = "pending"  # pending / running / done / error / cancelled
    events: List[SSEEvent] = field(default_factory=list)
    error_message: str = ""
    cancel_event: threading.Event = field(default_factory=threading.Event)
    new_event_signal: threading.Condition = field(default_factory=threading.Condition)
    created_at: float = field(default_factory=time.time)
    finished_at: Optional[float] = None

    def get_status(self) -> str:
        """get_status 获取任务当前状态。"""
        return self.status

    def is_finished(self) -> bool:
        """is_finished 判断任务是否已结束（含正常 / 异常 / 取消）。"""
        return self.status in {"done", "error", "cancelled"}

    def is_cancel_requested(self) -> bool:
        """is_cancel_requested 判断是否被请求取消。"""
        return self.cancel_event.is_set()

    def request_cancel(self) -> None:
        """request_cancel 标记任务取消，正在运行的循环应在合适位置主动退出。"""
        self.cancel_event.set()
        with self.new_event_signal:
            self.new_event_signal.notify_all()

    def append_event(self, event: SSEEvent) -> None:
        """append_event 追加事件并唤醒等待续连的消费者。"""
        with self.new_event_signal:
            self.events.append(event)
            self.new_event_signal.notify_all()
        logger.info(
            "task.append_event task_id=%s event_type=%s stage=%s total=%d",
            self.task_id, event.event_type, event.stage, len(self.events),
        )

    def mark_status(self, status: str, error_message: str = "") -> None:
        """mark_status 切换任务状态并通知等待方。"""
        self.status = status
        if error_message:
            self.error_message = error_message
        if status in {"done", "error", "cancelled"}:
            self.finished_at = time.time()
        with self.new_event_signal:
            self.new_event_signal.notify_all()


class TaskRegistry:
    """TaskRegistry 进程内任务注册表（按 task_id 索引）。"""

    def __init__(
        self,
        ttl_seconds: int = DEFAULT_TASK_TTL_SECONDS,
        max_tasks: int = DEFAULT_MAX_TASKS,
    ) -> None:
        self._tasks: Dict[str, ResearchTask] = {}
        self._lock = threading.Lock()
        self._ttl = ttl_seconds
        self._max_tasks = max_tasks

    def create_task(self, request: ResearchRequest) -> ResearchTask:
        """create_task 创建并登记一个新任务，返回任务对象。"""
        # 1. 清理过期任务，避免内存累积
        self._evict_expired_locked_safely()
        # 2. 若超出上限，淘汰最早完成的任务
        with self._lock:
            if len(self._tasks) >= self._max_tasks:
                finished = sorted(
                    (t for t in self._tasks.values() if t.is_finished()),
                    key=lambda t: t.finished_at or 0,
                )
                for old in finished[: max(1, len(self._tasks) - self._max_tasks + 1)]:
                    self._tasks.pop(old.task_id, None)
            task = ResearchTask(
                task_id=uuid.uuid4().hex,
                topic=request.get_topic(),
                request=request,
            )
            self._tasks[task.task_id] = task
            return task

    def get_task(self, task_id: str) -> Optional[ResearchTask]:
        """get_task 按 task_id 获取任务，未找到返回 None。"""
        with self._lock:
            return self._tasks.get(task_id)

    def stream_events(
        self,
        task_id: str,
        cursor: int = 0,
        wait_seconds: float = 30.0,
    ) -> Iterator[tuple[int, SSEEvent]]:
        """stream_events 按游标流式产出任务事件，含等待新事件的阻塞协程。

        - cursor 表示客户端已收到的事件个数，从 cursor 起继续推送
        - 当任务结束且无新事件时迭代终止
        - 单次等待最长 wait_seconds 秒，超时但任务仍在运行时输出心跳事件，
          保持长连接活性，避免 LLM 长耗时阻塞期间被前端误判为断流
        """
        task = self.get_task(task_id)
        if task is None:
            return
        idx = max(0, cursor)
        while True:
            # 1. 取下一条真实事件，或判断需要发心跳
            next_event: Optional[SSEEvent] = None
            send_heartbeat = False
            with task.new_event_signal:
                if idx >= len(task.events) and not task.is_finished():
                    task.new_event_signal.wait(timeout=wait_seconds)
                if idx < len(task.events):
                    next_event = task.events[idx]
                    idx += 1
                elif task.is_finished():
                    return
                else:
                    send_heartbeat = True
            # 2. 锁外 yield，避免阻塞 producer
            if next_event is not None:
                yield idx, next_event
                continue
            if send_heartbeat:
                yield idx, SSEEvent(
                    event_type="heartbeat",
                    stage="",
                    message="任务仍在运行...",
                    progress=0.0,
                    data={"task_id": task.task_id, "events_so_far": len(task.events)},
                )

    def _evict_expired_locked_safely(self) -> None:
        """_evict_expired_locked_safely 清理超过 TTL 的已完成任务。"""
        cutoff = time.time() - self._ttl
        with self._lock:
            stale_ids = [
                tid for tid, task in self._tasks.items()
                if task.is_finished() and (task.finished_at or task.created_at) < cutoff
            ]
            for tid in stale_ids:
                self._tasks.pop(tid, None)


_GLOBAL_REGISTRY: Optional[TaskRegistry] = None
_REGISTRY_LOCK = threading.Lock()
_CURRENT_TASK = threading.local()


def get_task_registry() -> TaskRegistry:
    """get_task_registry 获取进程级单例任务注册表。"""
    global _GLOBAL_REGISTRY
    if _GLOBAL_REGISTRY is None:
        with _REGISTRY_LOCK:
            if _GLOBAL_REGISTRY is None:
                _GLOBAL_REGISTRY = TaskRegistry()
    return _GLOBAL_REGISTRY


def set_current_task(task: Optional[ResearchTask]) -> None:
    """set_current_task 绑定当前 worker 线程对应的任务，便于子流程 emit 实时事件。"""
    if task is None:
        if hasattr(_CURRENT_TASK, "task"):
            delattr(_CURRENT_TASK, "task")
        return
    _CURRENT_TASK.task = task


def get_current_task() -> Optional[ResearchTask]:
    """get_current_task 读取当前 worker 线程绑定的任务，若不在 worker 中返回 None。"""
    return getattr(_CURRENT_TASK, "task", None)


def emit_progress(event: SSEEvent) -> None:
    """emit_progress 在长耗时节点内向当前任务推送实时进度事件（无任务上下文则忽略）。"""
    task = get_current_task()
    if task is None:
        return
    task.append_event(event)
