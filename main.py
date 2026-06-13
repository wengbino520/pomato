import sys
import os

# ── Windows DLL fix (must run BEFORE any PyQt6 import) ────────────────────────
# Anaconda ships vcruntime140_threads.dll 14.42.x in its root directory,
# which is searched BEFORE System32 and PATH entries.  Qt 6.11 requires
# 14.44.x.  Fix: pre-load the correct version from Qt6/bin via full path
# so Windows DLL cache locks onto it before Anaconda's copy is touched.
if sys.platform == "win32":
    import importlib.util, ctypes
    _spec = importlib.util.find_spec("PyQt6")
    if _spec and _spec.origin:
        _qt6_bin = os.path.join(os.path.dirname(_spec.origin), "Qt6", "bin")
        if os.path.isdir(_qt6_bin):
            os.add_dll_directory(_qt6_bin)
            # Pre-load newer runtime DLLs (order matters: leaves first)
            for _dll in [
                "concrt140.dll",
                "msvcp140.dll", "msvcp140_1.dll", "msvcp140_2.dll",
                "msvcp140_atomic_wait.dll", "msvcp140_codecvt_ids.dll",
                "vcruntime140.dll", "vcruntime140_1.dll",
                "vcruntime140_threads.dll",  # must be last / highest prio
            ]:
                _p = os.path.join(_qt6_bin, _dll)
                if os.path.exists(_p):
                    try:
                        ctypes.WinDLL(_p)
                    except OSError:
                        pass
# ──────────────────────────────────────────────────────────────────────────────

# Ensure project root is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication

from src.services.logger import setup_logging
from src.core.config import Config
from src.core.database import Database
from src.services.reminder_engine import ReminderEngine
from src.services.timer_engine import TimerEngine
from src.app import TrayManager


def main():
    setup_logging()   # 日志落盘到 ~/.pomato/logs/

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)   # Keep alive when all windows closed
    app.setApplicationName("POMATO")
    app.setApplicationDisplayName("POMATO 番茄日志")

    config = Config()
    db = Database()

    # ---- TASK-20: 初始化 ReminderEngine ----
    reminder_engine = ReminderEngine(config, db)
    timer = TimerEngine(config, reminder_engine=reminder_engine)
    timer.restore_session_no(db)   # NFR-03: restore today's count after restart

    tray = TrayManager(app, config, db, timer, reminder_engine=reminder_engine)
    tray.setup()

    timer.start()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
