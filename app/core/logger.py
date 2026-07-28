"""
统一日志系统

提供结构化日志记录，支持：
- 控制台输出（带颜色）
- 文件日志（按大小轮转）
- 日志级别控制
- 模块级日志器

用法:
    from app.core.logger import get_logger
    logger = get_logger(__name__)
    logger.info("消息")
    logger.error("错误", exc_info=True)
"""

import os
import sys
import json
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime

# 日志目录
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# 日志级别映射
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

# 默认日志级别
DEFAULT_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
DEFAULT_LEVEL = LOG_LEVELS.get(DEFAULT_LEVEL, logging.INFO)

# 缓存已创建的 logger
_loggers: dict[str, logging.Logger] = {}


class ColoredFormatter(logging.Formatter):
    """带颜色的控制台格式化器"""

    COLORS = {
        "DEBUG": "\033[36m",      # 青色
        "INFO": "\033[32m",       # 绿色
        "WARNING": "\033[33m",    # 黄色
        "ERROR": "\033[31m",      # 红色
        "CRITICAL": "\033[35m",   # 紫色
        "RESET": "\033[0m",       # 重置
    }

    def format(self, record: logging.LogRecord) -> str:
        level_color = self.COLORS.get(record.levelname, self.COLORS["RESET"])
        reset = self.COLORS["RESET"]

        # 时间戳
        timestamp = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")

        # 模块名（取最后两个包名）
        module = record.name
        if module.count(".") >= 2:
            parts = module.split(".")
            module = ".".join(parts[-2:])

        # 格式化消息
        if record.levelno >= logging.ERROR:
            return (
                f"{level_color}[{timestamp}]{reset} "
                f"{level_color}{record.levelname:<8}{reset} "
                f"[{module}] {record.getMessage()}"
            )
        elif record.levelno >= logging.WARNING:
            return (
                f"{level_color}[{timestamp}]{reset} "
                f"{level_color}{record.levelname:<8}{reset} "
                f"[{module}] {record.getMessage()}"
            )
        else:
            return (
                f"[{timestamp}] "
                f"{record.levelname:<8} "
                f"[{module}] {record.getMessage()}"
            )


class JsonFormatter(logging.Formatter):
    """JSON 格式化器（用于文件日志，方便日志分析）"""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "module": record.name,
            "message": record.getMessage(),
            "function": record.funcName,
            "line": record.lineno,
        }

        # 如果有异常信息，添加到日志
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
            }

        # 如果有额外字段（extra），添加到日志
        if hasattr(record, "extra_fields"):
            log_entry.update(record.extra_fields)

        return json.dumps(log_entry, ensure_ascii=False)


def get_logger(name: str, level: int | None = None) -> logging.Logger:
    """
    获取或创建模块级日志器

    Args:
        name: 模块名，通常传入 __name__
        level: 日志级别，默认使用全局配置

    Returns:
        logging.Logger 实例
    """
    if name in _loggers:
        return _loggers[name]

    logger = logging.getLogger(name)
    logger.setLevel(level or DEFAULT_LEVEL)
    logger.propagate = False  # 防止重复日志

    # 控制台 Handler（带颜色）
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level or DEFAULT_LEVEL)
    console_handler.setFormatter(ColoredFormatter())
    logger.addHandler(console_handler)

    # 文件 Handler（JSON 格式，按大小轮转）
    file_path = os.path.join(LOG_DIR, "aitem.log")
    file_handler = RotatingFileHandler(
        file_path,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(level or DEFAULT_LEVEL)
    file_handler.setFormatter(JsonFormatter())
    logger.addHandler(file_handler)

    # 错误日志单独文件
    error_path = os.path.join(LOG_DIR, "error.log")
    error_handler = RotatingFileHandler(
        error_path,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=3,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(JsonFormatter())
    logger.addHandler(error_handler)

    _loggers[name] = logger
    return logger


def set_level(level: str | int):
    """
    动态修改所有日志器的级别

    Args:
        level: 日志级别名称（如 "DEBUG"）或 logging 常量
    """
    if isinstance(level, str):
        level = LOG_LEVELS.get(level.upper(), logging.INFO)

    for logger in _loggers.values():
        logger.setLevel(level)
        for handler in logger.handlers:
            handler.setLevel(level)

    # 也修改根日志器
    root = logging.getLogger()
    root.setLevel(level)
    for handler in root.handlers:
        handler.setLevel(level)