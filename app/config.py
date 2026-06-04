"""config 配置管理。"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from app.constant.paper_constant import (
    DEFAULT_LLM_MODEL,
    DEFAULT_MAX_PAPER_COUNT,
    DEFAULT_MEMORY_PATH,
    DEFAULT_REQUEST_TIMEOUT_SECONDS,
)
from app.constant.report_constant import DEFAULT_REPORT_ARCHIVE_DIR


class Settings:
    """Settings 应用配置。"""

    def __init__(self) -> None:
        self.app_name = os.getenv("APP_NAME", "自动科研助手")
        self.log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper()
        self.memory_path = os.getenv("MEMORY_PATH", DEFAULT_MEMORY_PATH)
        self.report_archive_dir = os.getenv("REPORT_ARCHIVE_DIR", DEFAULT_REPORT_ARCHIVE_DIR)
        self.default_max_paper_count = int(
            os.getenv("DEFAULT_MAX_PAPER_COUNT", str(DEFAULT_MAX_PAPER_COUNT))
        )
        self.request_timeout_seconds = int(
            os.getenv(
                "REQUEST_TIMEOUT_SECONDS",
                str(DEFAULT_REQUEST_TIMEOUT_SECONDS),
            )
        )
        self.llm_base_url = os.getenv("LLM_BASE_URL", "").strip()
        self.llm_api_key = os.getenv("LLM_API_KEY", "").strip()
        self.llm_model = os.getenv("LLM_MODEL", DEFAULT_LLM_MODEL).strip()

    def get_app_name(self) -> str:
        """get_app_name 获取应用名称。"""
        return self.app_name

    def get_log_level(self) -> str:
        """get_log_level 获取日志级别。"""
        return self.log_level

    def get_memory_path(self) -> Path:
        """get_memory_path 获取记忆文件路径。"""
        return Path(self.memory_path)

    def get_report_archive_dir(self) -> Path:
        """get_report_archive_dir 获取报告归档目录。"""
        return Path(self.report_archive_dir)

    def get_default_max_paper_count(self) -> int:
        """get_default_max_paper_count 获取默认论文数。"""
        return self.default_max_paper_count

    def get_request_timeout_seconds(self) -> int:
        """get_request_timeout_seconds 获取请求超时时间。"""
        return self.request_timeout_seconds

    def get_llm_base_url(self) -> str:
        """get_llm_base_url 获取模型服务地址。"""
        return self.llm_base_url

    def get_llm_api_key(self) -> str:
        """get_llm_api_key 获取模型服务密钥。"""
        return self.llm_api_key

    def get_llm_model(self) -> str:
        """get_llm_model 获取模型名称。"""
        return self.llm_model

    def is_llm_enabled(self) -> bool:
        """is_llm_enabled 判断是否开启外部大模型。"""
        return bool(self.get_llm_base_url() and self.get_llm_api_key())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """get_settings 获取全局配置。"""
    return Settings()
