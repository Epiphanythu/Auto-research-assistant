"""test_task_registry.py 研究任务注册表测试。"""

from __future__ import annotations

import time

import pytest

from app.api_error import ActiveTaskLimitExceededError
from app.models.research_models import ResearchRequest
from app.services.infrastructure.task_registry import TaskRegistry


def _build_request(topic: str = "test task") -> ResearchRequest:
    """_build_request 构造最小研究请求。"""
    return ResearchRequest(topic=topic, max_papers=1)


class TestTaskRegistryConcurrency:
    """TestTaskRegistryConcurrency 验证后台任务并发保护。"""

    def test_create_task_blocks_when_active_limit_reached(self):
        """test_create_task_blocks_when_active_limit_reached 活跃任务达到上限时拒绝新任务。"""
        registry = TaskRegistry(max_active_tasks=1)
        task = registry.create_task(_build_request())
        task.mark_status("running")

        with pytest.raises(ActiveTaskLimitExceededError):
            registry.create_task(_build_request("another task"))

    def test_create_task_allows_after_task_finished(self):
        """test_create_task_allows_after_task_finished 任务结束后释放活跃名额。"""
        registry = TaskRegistry(max_active_tasks=1)
        task = registry.create_task(_build_request())
        task.mark_status("done")

        next_task = registry.create_task(_build_request("next task"))
        assert next_task.topic == "next task"
        assert registry.active_task_count() == 1

    def test_pending_task_also_counts_as_active(self):
        """test_pending_task_also_counts_as_active pending 任务也占用名额，避免 worker 启动前被绕过。"""
        registry = TaskRegistry(max_active_tasks=1)
        registry.create_task(_build_request())

        with pytest.raises(ActiveTaskLimitExceededError):
            registry.create_task(_build_request("queued task"))

    def test_expired_finished_task_is_evicted_before_capacity_check(self):
        """test_expired_finished_task_is_evicted_before_capacity_check 过期已完成任务不影响容量判断。"""
        registry = TaskRegistry(ttl_seconds=0, max_tasks=1, max_active_tasks=1)
        task = registry.create_task(_build_request())
        task.mark_status("done")
        time.sleep(0.01)

        next_task = registry.create_task(_build_request("fresh task"))
        assert next_task.topic == "fresh task"
