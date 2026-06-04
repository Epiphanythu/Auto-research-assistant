"""logging_config 日志初始化配置。"""

from __future__ import annotations

import logging

from app.config import get_settings

DEFAULT_LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
DEFAULT_LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging() -> None:
    """setup_logging 初始化应用统一日志配置。"""
    # 1. 统一读取日志级别，并规范化为 logging 模块支持的等级。
    settings = get_settings()
    log_level_name = settings.get_log_level()
    log_level = getattr(logging, log_level_name, logging.INFO)
    formatter = logging.Formatter(
        fmt=DEFAULT_LOG_FORMAT,
        datefmt=DEFAULT_LOG_DATE_FORMAT,
    )

    # 2. 若根日志器尚未配置 handler，则创建标准输出 handler；否则仅更新格式与级别。
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)
    else:
        for handler in root_logger.handlers:
            handler.setFormatter(formatter)
    root_logger.setLevel(log_level)

    # 3. 对 uvicorn 相关日志器同步级别，避免 Web 模式与 CLI 模式日志风格不一致。
    for logger_name in ["uvicorn", "uvicorn.error", "uvicorn.access"]:
        logging.getLogger(logger_name).setLevel(log_level)

    logging.getLogger(__name__).info(
        "Logging configured, app=%s, level=%s",
        settings.get_app_name(),
        log_level_name,
    )
