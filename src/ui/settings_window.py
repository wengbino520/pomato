from PyQt6.QtCore import Qt, QTime
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from src.services.logger import get_logger

logger = get_logger(__name__)


class SettingsWindow(QDialog):
    def __init__(self, config, parent=None, reminder_engine=None):
        super().__init__(parent)
        self.config = config
        self._reminder_engine = reminder_engine
        self._setup_ui()
        self._load_values()

    def _setup_ui(self):
        self.setWindowTitle("POMATO · 设置")
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
        self.resize(480, 440)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("⚙  设置")
        title.setStyleSheet("font-size:16px; font-weight:bold; color:#333;")
        layout.addWidget(title)

        tabs = QTabWidget()
        tabs.setStyleSheet(
            "QTabWidget::pane { border: 1px solid #ddd; border-radius: 6px;"
            " background: white; }"
            "QTabBar::tab { padding: 8px 18px; border: 1px solid #ddd;"
            " border-bottom: none; border-top-left-radius: 6px;"
            " border-top-right-radius: 6px; background: #f5f5f5;"
            " margin-right: 2px; }"
            "QTabBar::tab:selected { background: white; font-weight: bold; }"
        )

        # ── Tab 1: 计时 ─────────────────────────────────────────────
        timer_page = QWidget()
        t1 = QVBoxLayout(timer_page)
        t1.setContentsMargins(16, 16, 16, 16)

        timer_group = QGroupBox("工作时间与番茄钟")
        tf = QFormLayout(timer_group)

        self.start_time = QTimeEdit()
        self.start_time.setDisplayFormat("HH:mm")
        tf.addRow("每日开始时间：", self.start_time)

        self.end_time = QTimeEdit()
        self.end_time.setDisplayFormat("HH:mm")
        tf.addRow("每日截止时间：", self.end_time)

        self.pomodoro_dur = QSpinBox()
        self.pomodoro_dur.setRange(10, 60)
        self.pomodoro_dur.setSuffix(" 分钟")
        tf.addRow("番茄钟时长：", self.pomodoro_dur)

        self.short_break = QSpinBox()
        self.short_break.setRange(1, 15)
        self.short_break.setSuffix(" 分钟")
        tf.addRow("短休息时长：", self.short_break)

        self.long_break = QSpinBox()
        self.long_break.setRange(10, 30)
        self.long_break.setSuffix(" 分钟")
        tf.addRow("长休息时长：", self.long_break)

        self.long_interval = QSpinBox()
        self.long_interval.setRange(2, 8)
        self.long_interval.setSuffix(" 个番茄后")
        tf.addRow("长休息间隔：", self.long_interval)

        t1.addWidget(timer_group)
        t1.addStretch()
        tabs.addTab(timer_page, "  ⏱  计时  ")

        # ── Tab 2: AI 日报 ──────────────────────────────────────────
        ai_page = QWidget()
        a1 = QVBoxLayout(ai_page)
        a1.setContentsMargins(16, 16, 16, 16)

        ai_group = QGroupBox("AI 日报")
        af = QFormLayout(ai_group)

        self.api_base = QLineEdit()
        self.api_base.setPlaceholderText("https://api.openai.com/v1")
        af.addRow("API Base URL：", self.api_base)

        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key.setPlaceholderText("sk-…")
        af.addRow("API Key：", self.api_key)

        self.api_model = QLineEdit()
        self.api_model.setPlaceholderText("gpt-4o-mini")
        af.addRow("模型名称：", self.api_model)

        self.system_prompt = QTextEdit()
        self.system_prompt.setPlaceholderText("可选：自定义 AI 日报风格和结构要求")
        self.system_prompt.setMaximumHeight(120)
        af.addRow("日报模板 Prompt：", self.system_prompt)

        ollama_row = QHBoxLayout()
        ollama_hint = QLabel("本地模型：")
        ollama_btn = QPushButton("一键切换 Ollama")
        ollama_btn.setStyleSheet(
            "QPushButton{border:1px solid #ddd;border-radius:4px;padding:4px 10px;}"
            "QPushButton:hover{background:#f5f5f5;}"
        )
        ollama_btn.clicked.connect(self._apply_ollama_profile)
        ollama_row.addWidget(ollama_hint)
        ollama_row.addWidget(ollama_btn)
        ollama_row.addStretch()
        af.addRow("", ollama_row)

        a1.addWidget(ai_group)
        a1.addStretch()
        tabs.addTab(ai_page, "  🤖  AI 日报  ")

        # ── Tab 3: 提醒与标签 ───────────────────────────────────────
        rt_page = QWidget()
        r1 = QVBoxLayout(rt_page)
        r1.setContentsMargins(16, 16, 16, 16)

        if self._reminder_engine:
            reminder_group = QGroupBox("提醒管理")
            rl = QVBoxLayout(reminder_group)

            self.reminder_list = QListWidget()
            self.reminder_list.setMaximumHeight(130)
            self.reminder_list.setStyleSheet(
                "QListWidget{border:1px solid #ddd;border-radius:4px;}"
                "QListWidget::item{padding:4px;}"
            )
            rl.addWidget(self.reminder_list)

            btn_row = QHBoxLayout()
            add_r_btn = QPushButton("添加")
            add_r_btn.setStyleSheet(
                "QPushButton{background:#ef5350;color:white;border:none;"
                "border-radius:4px;padding:4px 12px;}"
                "QPushButton:hover{background:#e53935;}"
            )
            add_r_btn.clicked.connect(self._add_reminder)

            edit_r_btn = QPushButton("编辑")
            edit_r_btn.setStyleSheet(
                "QPushButton{border:1px solid #ddd;border-radius:4px;padding:4px 10px;}"
                "QPushButton:hover{background:#f5f5f5;}"
            )
            edit_r_btn.clicked.connect(self._edit_reminder)

            toggle_r_btn = QPushButton("启用/禁用")
            toggle_r_btn.setStyleSheet(
                "QPushButton{border:1px solid #ddd;border-radius:4px;padding:4px 10px;}"
                "QPushButton:hover{background:#f5f5f5;}"
            )
            toggle_r_btn.clicked.connect(self._toggle_reminder)

            del_r_btn = QPushButton("删除")
            del_r_btn.setStyleSheet(
                "QPushButton{border:1px solid #ddd;border-radius:4px;padding:4px 10px;}"
                "QPushButton:hover{background:#f5f5f5;}"
            )
            del_r_btn.clicked.connect(self._delete_reminder)

            btn_row.addWidget(add_r_btn)
            btn_row.addWidget(edit_r_btn)
            btn_row.addWidget(toggle_r_btn)
            btn_row.addWidget(del_r_btn)
            btn_row.addStretch()
            rl.addLayout(btn_row)
            r1.addWidget(reminder_group)
        else:
            self.reminder_list = None

        tags_group = QGroupBox("自定义标签")
        tl = QVBoxLayout(tags_group)

        self.tag_list = QListWidget()
        self.tag_list.setMaximumHeight(110)
        self.tag_list.setStyleSheet(
            "QListWidget{border:1px solid #ddd;border-radius:4px;}"
            "QListWidget::item{padding:4px;}"
            "QListWidget::item:selected{background:#ffebee;color:#d32f2f;}"
        )
        tl.addWidget(self.tag_list)

        tag_input_row = QHBoxLayout()
        self.new_tag_input = QLineEdit()
        self.new_tag_input.setPlaceholderText("新标签名称…")
        self.new_tag_input.returnPressed.connect(self._add_tag)
        add_tag_btn = QPushButton("添加")
        add_tag_btn.setStyleSheet(
            "QPushButton{background:#ef5350;color:white;border:none;"
            "border-radius:4px;padding:5px 14px;}"
            "QPushButton:hover{background:#e53935;}"
        )
        add_tag_btn.clicked.connect(self._add_tag)
        del_tag_btn = QPushButton("删除选中")
        del_tag_btn.setStyleSheet(
            "QPushButton{border:1px solid #ddd;border-radius:4px;padding:5px 10px;}"
            "QPushButton:hover{background:#f5f5f5;}"
        )
        del_tag_btn.clicked.connect(self._del_tag)
        tag_input_row.addWidget(self.new_tag_input)
        tag_input_row.addWidget(add_tag_btn)
        tag_input_row.addWidget(del_tag_btn)
        tl.addLayout(tag_input_row)
        r1.addWidget(tags_group)
        r1.addStretch()
        tabs.addTab(rt_page, "  🔔  提醒与标签  ")

        # ── Tab 4: 其他 ─────────────────────────────────────────────
        misc_page = QWidget()
        m1 = QVBoxLayout(misc_page)
        m1.setContentsMargins(16, 16, 16, 16)

        misc_group = QGroupBox("通用选项")
        mf = QFormLayout(misc_group)
        self.sound_enabled = QCheckBox("启用提示音")
        mf.addRow("", self.sound_enabled)

        self.autostart_enabled = QCheckBox("开机自启动")
        mf.addRow("", self.autostart_enabled)

        self.holiday_check = QCheckBox("自动识别法定节假日（非工作日不计时）")
        self.holiday_check.setToolTip(
            "通过 timor.tech API 获取中国法定节假日数据，\n法定假日及调休日自动识别。"
        )
        mf.addRow("", self.holiday_check)

        self.popup_timeout = QSpinBox()
        self.popup_timeout.setRange(30, 600)
        self.popup_timeout.setSuffix(" 秒")
        mf.addRow("弹窗自动超时：", self.popup_timeout)

        self.todo_carry_over = QCheckBox("未完成待办自动结转至次日")
        mf.addRow("", self.todo_carry_over)

        self.reminder_silent = QCheckBox("非工作时间提醒静默")
        mf.addRow("", self.reminder_silent)

        self.reminder_timeout = QSpinBox()
        self.reminder_timeout.setRange(30, 600)
        self.reminder_timeout.setSuffix(" 秒")
        mf.addRow("提醒弹窗超时：", self.reminder_timeout)

        m1.addWidget(misc_group)
        m1.addStretch()
        tabs.addTab(misc_page, "  ⚙  其他  ")

        layout.addWidget(tabs, 1)

        # ── Buttons ────────────────────────────────────────────────────
        bl = QHBoxLayout()
        cancel_btn = QPushButton("取消")
        cancel_btn.setStyleSheet(
            "QPushButton { border:1px solid #ddd; border-radius:5px;"
            "  padding:8px 20px; background:white; }"
            "QPushButton:hover { background:#f5f5f5; }"
        )
        cancel_btn.clicked.connect(self.reject)

        save_btn = QPushButton("保存")
        save_btn.setStyleSheet(
            "QPushButton { background:#ef5350; color:white; border:none;"
            "  border-radius:5px; padding:8px 20px; font-weight:bold; }"
            "QPushButton:hover { background:#e53935; }"
        )
        save_btn.clicked.connect(self._save)

        bl.addStretch()
        bl.addWidget(cancel_btn)
        bl.addWidget(save_btn)
        layout.addLayout(bl)

    def _load_values(self):
        start = self.config.get("work_start_time", "08:30")
        h, m = map(int, start.split(":"))
        self.start_time.setTime(QTime(h, m))

        end = self.config.get("work_end_time", "22:30")
        eh, em = map(int, end.split(":"))
        self.end_time.setTime(QTime(eh, em))

        self.pomodoro_dur.setValue(self.config.get("pomodoro_duration", 25))
        self.short_break.setValue(self.config.get("short_break_duration", 5))
        self.long_break.setValue(self.config.get("long_break_duration", 15))
        self.long_interval.setValue(self.config.get("long_break_interval", 4))

        self.api_base.setText(self.config.get("api_base_url", ""))
        self.api_key.setText(self.config.get("api_key", ""))
        self.api_model.setText(self.config.get("api_model", "gpt-4o-mini"))
        self.system_prompt.setPlainText(self.config.get("report_system_prompt", ""))
        self.sound_enabled.setChecked(self.config.get("sound_enabled", True))
        self.autostart_enabled.setChecked(self.config.get("autostart_enabled", True))
        self.holiday_check.setChecked(self.config.get("holiday_check_enabled", True))
        self.popup_timeout.setValue(self.config.get("popup_timeout_seconds", 180))

        # TASK-18: 新配置项
        self.todo_carry_over.setChecked(self.config.get("todo_auto_carry_over", True))
        self.reminder_silent.setChecked(self.config.get("reminder_silent_outside_work", False))
        self.reminder_timeout.setValue(self.config.get("reminder_popup_timeout_seconds", 120))

        # TASK-19: 刷新提醒列表
        self._refresh_reminder_list()

        self.tag_list.clear()
        for tag in self.config.get("custom_tags", []):
            self.tag_list.addItem(tag)

    def _save(self):
        logger.info("Settings save requested")
        t = self.start_time.time()
        self.config.set("work_start_time", f"{t.hour():02d}:{t.minute():02d}")
        et = self.end_time.time()
        self.config.set("work_end_time", f"{et.hour():02d}:{et.minute():02d}")
        self.config.set("pomodoro_duration", self.pomodoro_dur.value())
        self.config.set("short_break_duration", self.short_break.value())
        self.config.set("long_break_duration", self.long_break.value())
        self.config.set("long_break_interval", self.long_interval.value())
        self.config.set("api_base_url", self.api_base.text().strip())
        self.config.set("api_key", self.api_key.text().strip())
        self.config.set("api_model", self.api_model.text().strip())
        self.config.set("report_system_prompt", self.system_prompt.toPlainText().strip())
        self.config.set("sound_enabled", self.sound_enabled.isChecked())
        self.config.set("autostart_enabled", self.autostart_enabled.isChecked())
        self.config.set("holiday_check_enabled", self.holiday_check.isChecked())
        self.config.set("popup_timeout_seconds", self.popup_timeout.value())
        self.config.set("todo_auto_carry_over", self.todo_carry_over.isChecked())
        self.config.set("reminder_silent_outside_work", self.reminder_silent.isChecked())
        self.config.set("reminder_popup_timeout_seconds", self.reminder_timeout.value())
        self.config.sync_autostart()
        tags = []
        for i in range(self.tag_list.count()):
            item = self.tag_list.item(i)
            if item is not None:
                tags.append(item.text())
        self.config.set("custom_tags", tags)
        logger.info("Settings saved successfully")
        QMessageBox.information(self, "保存成功", "设置已保存！重启后生效（计时参数下轮番茄钟生效）。")
        self.accept()

    def _add_tag(self):
        name = self.new_tag_input.text().strip()
        if not name:
            return
        existing = []
        for i in range(self.tag_list.count()):
            item = self.tag_list.item(i)
            if item is not None:
                existing.append(item.text())
        if name not in existing:
            self.tag_list.addItem(name)
        self.new_tag_input.clear()

    def _del_tag(self):
        row = self.tag_list.currentRow()
        if row >= 0:
            self.tag_list.takeItem(row)

    def _apply_ollama_profile(self):
        self.api_base.setText("http://localhost:11434/v1")
        self.api_key.setText("")
        if not self.api_model.text().strip() or self.api_model.text().strip() == "gpt-4o-mini":
            self.api_model.setText("qwen2.5:7b")

    # ------------------------------------------------------------------
    # TASK-19: 提醒管理 CRUD
    # ------------------------------------------------------------------

    def _refresh_reminder_list(self):
        if not hasattr(self, "reminder_list") or not self._reminder_engine:
            return
        self.reminder_list.clear()
        reminders = self._reminder_engine.get_all_reminders()
        for r in reminders:
            enabled = "🔔" if r.get("enabled", 1) else "🔕"
            item = QListWidgetItem(
                f"{enabled} {r['remind_time']}  {r['title']}"
            )
            item.setData(Qt.ItemDataRole.UserRole, r["id"])
            if not r.get("enabled", 1):
                item.setForeground(Qt.GlobalColor.gray)
            self.reminder_list.addItem(item)

    def _add_reminder(self):
        if not self._reminder_engine:
            return
        dlg = _ReminderEditDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            if not data["title"]:
                return
            self._reminder_engine.add_reminder(**data)
            self._refresh_reminder_list()

    def _edit_reminder(self):
        if not self._reminder_engine:
            return
        item = self.reminder_list.currentItem()
        if not item:
            return
        rid = item.data(Qt.ItemDataRole.UserRole)
        r = self._reminder_engine.db.get_reminder(rid)
        if not r:
            return
        dlg = _ReminderEditDialog(
            self, title=r["title"], remind_time=r["remind_time"],
            repeat_type=r.get("repeat_type", "none"),
            repeat_days=r.get("repeat_days", ""),
            snooze_min=r.get("snooze_min", 10),
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            if not data["title"]:
                return
            self._reminder_engine.update_reminder(rid, **data)
            self._refresh_reminder_list()

    def _toggle_reminder(self):
        if not self._reminder_engine:
            return
        item = self.reminder_list.currentItem()
        if not item:
            return
        rid = item.data(Qt.ItemDataRole.UserRole)
        r = self._reminder_engine.db.get_reminder(rid)
        if r:
            self._reminder_engine.update_reminder(rid, enabled=0 if r["enabled"] else 1)
            self._refresh_reminder_list()

    def _delete_reminder(self):
        if not self._reminder_engine:
            return
        item = self.reminder_list.currentItem()
        if not item:
            return
        rid = item.data(Qt.ItemDataRole.UserRole)
        reply = QMessageBox.question(
            self, "删除提醒", "确定要删除这个提醒吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._reminder_engine.delete_reminder(rid)
            self._refresh_reminder_list()


class _ReminderEditDialog(QDialog):
    """内嵌提醒编辑弹窗。"""

    def __init__(self, parent=None, title="", remind_time=None,
                 repeat_type="none", repeat_days="", snooze_min=10):
        super().__init__(parent)
        self.setWindowTitle("提醒")
        self.setMinimumWidth(300)
        self.setModal(True)

        from PyQt6.QtWidgets import QComboBox
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        layout.addWidget(QLabel("标题："))
        self.title_edit = QLineEdit(title)
        self.title_edit.setPlaceholderText("提醒内容...")
        layout.addWidget(self.title_edit)

        layout.addWidget(QLabel("时间："))
        self.time_edit = QTimeEdit()
        if remind_time:
            h, m = map(int, remind_time.split(":"))
            self.time_edit.setTime(QTime(h, m))
        self.time_edit.setDisplayFormat("HH:mm")
        layout.addWidget(self.time_edit)

        layout.addWidget(QLabel("重复："))
        self.repeat_combo = QComboBox()
        self.repeat_combo.addItems(["不重复", "每天", "每周", "工作日"])
        type_map = {"none": 0, "daily": 1, "weekly": 2, "weekday": 3}
        self.repeat_combo.setCurrentIndex(type_map.get(repeat_type, 0))
        layout.addWidget(self.repeat_combo)

        layout.addWidget(QLabel("延后（分钟）："))
        self.snooze_spin = QSpinBox()
        self.snooze_spin.setRange(1, 120)
        self.snooze_spin.setValue(snooze_min)
        layout.addWidget(self.snooze_spin)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get_data(self):
        type_map = {0: "none", 1: "daily", 2: "weekly", 3: "weekday"}
        return {
            "title": self.title_edit.text().strip(),
            "remind_time": self.time_edit.time().toString("HH:mm"),
            "repeat_type": type_map[self.repeat_combo.currentIndex()],
            "snooze_min": self.snooze_spin.value(),
        }
