"""
POMATO 统一日志模块。

用法:
    from src.services.logger import get_logger
    logger = get_logger(__name__)
    logger.info("something happened")
    logger.exception("unexpected error")    # 自动附带 traceback

配置:
    控制台: INFO 及以上（以 QApplication 运行时跳过，避免干扰 GUI 输出）
    文件:   DEBUG 及以上，按天轮转，存储在 ~/.pomato/logs/ 下
"""

import logging
import sys
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

_LOG_INITIALIZED = False
_LOG_DIR: Path | None = None


def setup_logging(log_dir: str | Path = "", *, console: bool = False) -> None:
    """初始化根日志配置（应在 main.py 入口尽早调用）。

    Args:
        log_dir:  日志目录，默认 ~/.pomato/logs/
        console:  是否输出到控制台（CLI 调试时可用）
    """
    global _LOG_INITIALIZED, _LOG_DIR

    if _LOG_INITIALIZED:
        return

    if not log_dir:
        log_dir = Path.home() / ".pomato" / "logs"
    else:
        log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    _LOG_DIR = log_dir

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.handlers.clear()

    # 格式
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 文件 handler —— DEBUG 级别，按天旋转，保留 90 天
    file_handler = TimedRotatingFileHandler(
        filename=log_dir / "pomato.log",
        when="midnight",
        interval=1,
        backupCount=90,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    # 控制台 handler —— INFO 级别，仅 CLI 模式开启
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(fmt)
        root.addHandler(console_handler)

    # 写入分隔线，标记新会话
    logging.info("─" * 60)
    logging.info("POMATO session started at %s", datetime.now().isoformat())
    logging.info("Log file: %s", file_handler.baseFilename)

    _LOG_INITIALIZED = True


def get_log_dir() -> str:
    """返回日志目录路径，未初始化时返回空字符串。"""
    return str(_LOG_DIR) if _LOG_DIR else ""


def get_logger(name: str) -> logging.Logger:
    """获取指定模块的 logger（自动继承根日志配置）。

    如果 setup_logging 未调用，自动以默认配置初始化。
    """
    if not _LOG_INITIALIZED:
        setup_logging()
    return logging.getLogger(name)
