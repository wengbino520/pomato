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
            os.add_dll_directory(_qt6_bin)
# ──────────────────────────────────────────────────────────────────────────────

# Ensure project root is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication

from src.config import Config
from src.database import Database
from src.timer_engine import TimerEngine
from src.tray_manager import TrayManager


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)   # Keep alive when all windows closed
    app.setApplicationName("POMATO")
    app.setApplicationDisplayName("POMATO 番茄日志")

    config = Config()
    db = Database()
    timer = TimerEngine(config)

    tray = TrayManager(app, config, db, timer)
    tray.setup()

    timer.start()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
