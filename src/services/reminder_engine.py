"""
reminder_engine.py — 待办管理 + 定时提醒引擎

设计原则：
- 零新线程，复用 TimerEngine 的 1s QTimer tick
- 内存中维护已加载的提醒列表，tick 时仅做时间比较
- 提醒触发信号通过 TrayManager 连接到弹窗
"""
from datetime import datetime, date, timedelta
from enum import Enum
from PyQt6.QtCore import QObject, pyqtSignal

from src.services.logger import get_logger

logger = get_logger(__name__)


class TodoStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class RepeatType(str, Enum):
    NONE = "none"
    DAILY = "daily"
    WEEKLY = "weekly"
    WEEKDAY = "weekday"


class ReminderEngine(QObject):
    # ---- 信号 ----
    reminder_triggered = pyqtSignal(int, str, str)  # (reminder_id, title, remind_time_str)
    todos_changed = pyqtSignal()

    def __init__(self, config, db):
        super().__init__()
        self.config = config
        self.db = db
        self._reminders: list[dict] = []
        self._triggered_today: set[int] = set()
        self._last_date: str | None = None
        self._reload_reminders()

    # ================================================================
    # 提醒管理 (TASK-06)
    # ================================================================

    def _reload_reminders(self):
        """从 DB 重载所有启用的提醒到内存。"""
        today = date.today().isoformat()
        self._reminders = self.db.get_enabled_reminders()
        # 清理跨天过期的 snoozed_until
        for r in self._reminders:
            su = r.get("snoozed_until")
            if su and su[:10] < today:
                self.db.update_reminder(r["id"], snoozed_until=None)
                r["snoozed_until"] = None
                logger.debug("Cleared expired snooze for reminder id=%d", r["id"])
        self._triggered_today = {
            r["id"] for r in self._reminders
            if r.get("last_triggered") == today
        }
        logger.debug("Reminders reloaded: %d enabled, %d triggered today", len(self._reminders), len(self._triggered_today))

    def add_reminder(self, title, remind_time, remind_date=None,
                     repeat_type="none", repeat_days="", snooze_min=10):
        rid = self.db.add_reminder(title, remind_time, remind_date,
                                   repeat_type, repeat_days, snooze_min)
        self._reload_reminders()
        return rid

    def update_reminder(self, reminder_id, **kwargs):
        self.db.update_reminder(reminder_id, **kwargs)
        self._reload_reminders()

    def delete_reminder(self, reminder_id):
        self.db.delete_reminder(reminder_id)
        self._reload_reminders()

    def get_all_reminders(self):
        return self.db.get_all_reminders()

    def snooze_reminder(self, reminder_id):
        """延后提醒。不修改 remind_time，仅设置 snoozed_until 临时跳过窗口。"""
        r = self.db.get_reminder(reminder_id)
        if not r:
            return
        snooze_min = r.get("snooze_min", 10)
        now = datetime.now()
        snoozed_until = (now + timedelta(minutes=snooze_min)).isoformat()
        self.db.update_reminder(reminder_id,
                                snoozed_until=snoozed_until,
                                last_triggered=None)
        self._reload_reminders()

    # ================================================================
    # 待办管理 (TASK-05)
    # ================================================================

    def add_todo(self, title, priority=1, due_date=None, note="",
                 todo_date=None):
        tid = self.db.add_todo(title, priority, due_date, note, todo_date)
        self.todos_changed.emit()
        return tid

    def update_todo(self, todo_id, **kwargs):
        self.db.update_todo(todo_id, **kwargs)
        self.todos_changed.emit()

    def delete_todo(self, todo_id):
        self.db.delete_todo(todo_id)
        self.todos_changed.emit()

    def get_todos(self, date_str=None, include_done=True):
        return self.db.get_todos(date_str=date_str, include_done=include_done)

    def reorder_todos(self, ordered_ids):
        self.db.reorder_todos(ordered_ids)
        self.todos_changed.emit()

    # ================================================================
    # 每秒 tick（由 TimerEngine 的 QTimer 触发）(TASK-06)
    # ================================================================

    def on_tick(self):
        """在 TimerEngine._on_tick() 末尾调用。"""
        now = datetime.now()
        today_str = now.date().isoformat()
        current_time_str = f"{now.hour:02d}:{now.minute:02d}"
        weekday = now.weekday()  # 0=Mon

        # ---- 日期变更检测 ----
        if self._last_date is not None and self._last_date != today_str:
            self._reload_reminders()
        self._last_date = today_str

        # ---- 非工作时间静默 ----
        if self.config.get("reminder_silent_outside_work", False):
            work_start = self.config.get("work_start_time", "08:30")
            work_end = self.config.get("work_end_time", "22:30")
            if not (work_start <= current_time_str <= work_end):
                return

        # ---- 扫描提醒 ----
        for r in self._reminders:
            if r["id"] in self._triggered_today:
                continue

            # Snooze 窗口检查：在延后期间跳过
            snoozed_until = r.get("snoozed_until")
            if snoozed_until:
                if now.isoformat() < snoozed_until:
                    continue
                # Snooze 窗口已过期，清除状态
                self.db.update_reminder(r["id"], snoozed_until=None)
                r["snoozed_until"] = None
                logger.debug("Snooze expired for reminder id=%d", r["id"])

            if r["remind_time"] != current_time_str:
                continue

            repeat_type = r.get("repeat_type", "none")
            remind_date = r.get("remind_date")

            # One-time dated reminder: skip if date doesn't match
            if repeat_type == RepeatType.NONE and remind_date:
                if remind_date != today_str:
                    continue
            elif repeat_type == RepeatType.WEEKDAY and weekday >= 5:
                continue
            elif repeat_type == RepeatType.WEEKLY:
                days = r.get("repeat_days", "").split(",")
                if str(weekday) not in days:
                    continue

            # 触发！
            logger.info("Reminder triggered: id=%d title=%s", r["id"], r["title"])
            self.db.mark_reminder_triggered(r["id"], today_str)
            self._triggered_today.add(r["id"])
            self.reminder_triggered.emit(r["id"], r["title"], r["remind_time"])
