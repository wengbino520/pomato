"""
POMATO — 番茄日志桌面应用

四层架构：
  src/core/       L1 基础设施 — Config, Database
  src/services/   L2 业务逻辑 — AIClient, HolidayManager, TimerEngine, ReminderEngine
  src/ui/         L3 表示层   — 弹窗、窗口、组件
  src/app.py      L4 编排层   — TrayManager (系统托盘 + 模块装配)
  src/main.py     入口       — QApplication 启动
"""
