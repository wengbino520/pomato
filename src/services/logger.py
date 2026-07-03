"""
POMATO 统一日志模块。

用法:
    from src.services.logger import get_logger
    logger = get_logger(__name__)
    logger.info("something happened", extra={"session": 3})
    logger.exception("unexpected error")    # 自动附带 traceback

配置:
    控制台: INFO 及以上，文本格式
    文件:   DEBUG 及以上，JSON 结构化格式，按天轮转，存储在 ~/.pomato/logs/
"""

import json
import logging
import sys
from datetime import datetime, timezone
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

_LOG_INITIALIZED = False
_LOG_DIR: Path | None = None


class JsonFormatter(logging.Formatter):
    """将日志记录序列化为 JSON 行，便于结构化查询和分析 (ID-01)。

    输出格式每行一个 JSON 对象::

        {"ts":"2026-06-14T09:15:00.123Z","level":"INFO","name":"src.app","msg":"..."}
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + f"{datetime.now(timezone.utc).microsecond // 1000:03d}Z",
            "level": record.levelname,
            "name": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info and record.exc_info[1]:
            log_entry["exc"] = self.formatException(record.exc_info)
        # 注入通过 extra= 传入的自定义字段
        for key in ("session", "todo_id", "elapsed", "state", "duration_ms"):
            val = getattr(record, key, None)
            if val is not None:
                log_entry[key] = val
        return json.dumps(log_entry, ensure_ascii=False)


def setup_logging(log_dir: str | Path = "", *, console: bool = False, force: bool = False) -> None:
    """初始化根日志配置（应在 main.py 入口尽早调用）。

    Args:
        log_dir:  日志目录，默认 ~/.pomato/logs/
        console:  是否输出到控制台（CLI 调试时可用）
    """
    global _LOG_INITIALIZED, _LOG_DIR

    if _LOG_INITIALIZED and not force:
        return

    if not log_dir:
        log_dir = Path.home() / ".pomato" / "logs"
    else:
        log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    _LOG_DIR = log_dir

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    for handler in root.handlers:
        try:
            handler.close()
        except Exception:
            pass
    root.handlers.clear()

    # 文件 handler —— DEBUG 级别，JSON 格式，按天旋转，保留 90 天 (ID-01)
    file_handler = TimedRotatingFileHandler(
        filename=log_dir / "pomato.log",
        when="midnight",
        interval=1,
        backupCount=90,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(JsonFormatter())
    root.addHandler(file_handler)

    # 控制台 handler —— INFO 级别，文本格式，仅 CLI 模式开启
    if console:
        console_fmt = logging.Formatter(
            "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(console_fmt)
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

    日志实例可在 setup_logging 调用前安全获取；真正的 handler 由入口统一配置。
    """
    return logging.getLogger(name)
