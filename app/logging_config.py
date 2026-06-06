"""logging_config 日志初始化配置。"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler

from app.config import get_settings

DEFAULT_LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
DEFAULT_LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging() -> None:
    """setup_logging 初始化应用统一日志配置（含落盘滚动）。"""
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
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        root_logger.addHandler(stream_handler)
    else:
        for handler in root_logger.handlers:
            handler.setFormatter(formatter)
    root_logger.setLevel(log_level)

    # 3. 日志落盘：按体积滚动，最多保留 backup_count 份历史。
    log_file_path = settings.get_log_file_path()
    if log_file_path:
        try:
            os.makedirs(os.path.dirname(os.path.abspath(log_file_path)) or ".", exist_ok=True)
            already = any(
                isinstance(h, RotatingFileHandler) and getattr(h, "baseFilename", "") == os.path.abspath(log_file_path)
                for h in root_logger.handlers
            )
            if not already:
                file_handler = RotatingFileHandler(
                    log_file_path,
                    maxBytes=settings.get_log_file_max_bytes(),
                    backupCount=settings.get_log_file_backup_count(),
                    encoding="utf-8",
                )
                file_handler.setFormatter(formatter)
                root_logger.addHandler(file_handler)
        except OSError:
            # 落盘失败不应阻塞应用启动，仅在 stdout 提示
            logging.getLogger(__name__).warning(
                "Log file handler init failed, path=%s", log_file_path,
            )

    # 4. 对 uvicorn 相关日志器同步级别，避免 Web 模式与 CLI 模式日志风格不一致。
    for logger_name in ["uvicorn", "uvicorn.error", "uvicorn.access"]:
        logging.getLogger(logger_name).setLevel(log_level)

    logging.getLogger(__name__).info(
        "Logging configured, app=%s, level=%s, file=%s",
        settings.get_app_name(),
        log_level_name,
        log_file_path or "stdout-only",
    )
