"""
共享测试夹具（fixtures）。
"""
import sys
import json
from pathlib import Path
from unittest.mock import patch

import pytest

# 确保项目根目录在 sys.path，使 `from src.xxx import ...` 可用
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ── Qt Application ────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def qapp():
    """
    会话级 QApplication。
    QObject / QTimer 的实例化需要 QApplication 存在。
    """
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv[:1])
    yield app


# ── Config ────────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_config(tmp_path):
    """
    指向临时目录的 Config 实例，与真实 ~/.pomato 完全隔离。
    """
    with patch("pathlib.Path.home", return_value=tmp_path):
        from src.config import Config
        return Config()


# ── Database ──────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_db(tmp_path):
    """
    指向临时目录的 Database 实例，使用独立 SQLite 文件。
    """
    with patch("pathlib.Path.home", return_value=tmp_path):
        from src.database import Database
        return Database()


# ── TimerEngine ───────────────────────────────────────────────────────────────

@pytest.fixture
def engine(qapp, tmp_config):
    """
    TimerEngine 实例，使用隔离配置，QTimer 未启动。
    """
    from src.timer_engine import TimerEngine
    return TimerEngine(tmp_config)


# ── ReminderEngine ────────────────────────────────────────────────────────────

@pytest.fixture
def reminder_engine(qapp, tmp_config, tmp_db):
    """
    ReminderEngine 实例，使用隔离 Config + Database。
    """
    from src.reminder_engine import ReminderEngine
    return ReminderEngine(tmp_config, tmp_db)
