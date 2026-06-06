from PyQt6.QtCore import Qt, QTime
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTextEdit,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)


class SettingsWindow(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self._setup_ui()
        self._load_values()

    def _setup_ui(self):
        self.setWindowTitle("POMATO · 设置")
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
        self.resize(460, 580)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("⚙  设置")
        title.setStyleSheet("font-size:16px; font-weight:bold; color:#333;")
        layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border:none; }")

        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setSpacing(12)

        # ── Timer settings ─────────────────────────────────────────────
        timer_group = QGroupBox("计时设置")
        tf = QFormLayout(timer_group)

        self.start_time = QTimeEdit()
        self.start_time.setDisplayFormat("HH:mm")
        tf.addRow("每日开始时间：", self.start_time)

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

        cl.addWidget(timer_group)

        # ── AI settings ────────────────────────────────────────────────
        ai_group = QGroupBox("AI 设置")
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

        cl.addWidget(ai_group)

        # ── Misc ────────────────────────────────────────────────────────
        misc_group = QGroupBox("其他")
        mf = QFormLayout(misc_group)
        self.sound_enabled = QCheckBox("启用提示音")
        mf.addRow("", self.sound_enabled)

        self.autostart_enabled = QCheckBox("开机自启动")
        mf.addRow("", self.autostart_enabled)

        self.holiday_check = QCheckBox("自动识别法定节假日（非工作日不计时）")
        self.holiday_check.setToolTip("通过 timor.tech API 获取中国法定节假日数据，\n法定假日及调休日自动识别。")
        mf.addRow("", self.holiday_check)

        self.popup_timeout = QSpinBox()
        self.popup_timeout.setRange(30, 600)
        self.popup_timeout.setSuffix(" 秒")
        mf.addRow("弹窗自动超时：", self.popup_timeout)
        cl.addWidget(misc_group)

        # ── Tags ────────────────────────────────────────────────────────
        tags_group = QGroupBox("自定义标签")
        tl = QVBoxLayout(tags_group)

        self.tag_list = QListWidget()
        self.tag_list.setMaximumHeight(120)
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
        cl.addWidget(tags_group)

        cl.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

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

        self.tag_list.clear()
        for tag in self.config.get("custom_tags", []):
            self.tag_list.addItem(tag)

    def _save(self):
        t = self.start_time.time()
        self.config.set("work_start_time", f"{t.hour():02d}:{t.minute():02d}")
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
        self.config.sync_autostart()
        tags = []
        for i in range(self.tag_list.count()):
            item = self.tag_list.item(i)
            if item is not None:
                tags.append(item.text())
        self.config.set("custom_tags", tags)
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
