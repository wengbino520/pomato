from PyQt6.QtCore import Qt, QTime
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
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
        self.resize(460, 540)

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

        cl.addWidget(ai_group)

        # ── Misc ────────────────────────────────────────────────────────
        misc_group = QGroupBox("其他")
        mf = QFormLayout(misc_group)
        self.sound_enabled = QCheckBox("启用提示音")
        mf.addRow("", self.sound_enabled)
        cl.addWidget(misc_group)

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
        self.sound_enabled.setChecked(self.config.get("sound_enabled", True))

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
        self.config.set("sound_enabled", self.sound_enabled.isChecked())
        QMessageBox.information(self, "保存成功", "设置已保存！重启后生效（计时参数下轮番茄钟生效）。")
        self.accept()
