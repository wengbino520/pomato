import sys
import os
import argparse
from dataclasses import dataclass
from pathlib import Path

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
from src.core.profile_manager import ProfileManager


@dataclass(frozen=True)
class RuntimeContext:
    data_dir: Path
    log_dir: Path
    profile_id: str | None
    source: str
    profile_manager: ProfileManager | None = None


def parse_runtime_args(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--profile", dest="profile_id")
    parser.add_argument("--data-dir", dest="data_dir")
    return parser.parse_args(argv or [])


def resolve_runtime_context(argv: list[str] | None = None, app_root: Path | None = None) -> RuntimeContext:
    args = parse_runtime_args(argv)

    if args.data_dir:
        data_dir = Path(args.data_dir)
        return RuntimeContext(
            data_dir=data_dir,
            log_dir=data_dir / "logs",
            profile_id=None,
            source="data-dir",
            profile_manager=None,
        )

    manager = ProfileManager(app_root=app_root)
    if args.profile_id:
        if not manager.has_profile(args.profile_id):
            raise ValueError(f"资料空间不存在: {args.profile_id}")
        profile_id = args.profile_id
        source = "profile"
    else:
        profile_id = manager.get_active_profile_id()
        if not manager.has_profile(profile_id):
            raise ValueError(f"资料空间不存在: {profile_id}")
        source = "active-profile"

    paths = manager.get_profile_paths(profile_id)
    return RuntimeContext(
        data_dir=paths.data_dir,
        log_dir=paths.log_dir,
        profile_id=profile_id,
        source=source,
        profile_manager=manager,
    )


def main(argv: list[str] | None = None):
    runtime_argv = list(argv) if argv is not None else sys.argv[1:]
    context = resolve_runtime_context(runtime_argv)
    setup_logging(log_dir=context.log_dir, force=True)

    from src.core.config import Config
    from src.core.database import Database
    from src.services.reminder_engine import ReminderEngine
    from src.services.timer_engine import TimerEngine
    from src.app import TrayManager

    app = QApplication([sys.argv[0], *runtime_argv])
    app.setQuitOnLastWindowClosed(False)   # Keep alive when all windows closed
    app.setApplicationName("POMATO")
    app.setApplicationDisplayName("POMATO 番茄日志")

    config = Config(data_dir=context.data_dir)
    db = Database(data_dir=context.data_dir)

    # ---- TASK-20: 初始化 ReminderEngine ----
    reminder_engine = ReminderEngine(config, db)
    timer = TimerEngine(config, reminder_engine=reminder_engine)
    timer.restore_session_no(db)   # NFR-03: restore today's count after restart

    tray = TrayManager(
        app,
        config,
        db,
        timer,
        reminder_engine=reminder_engine,
        profile_manager=context.profile_manager,
        runtime_args=runtime_argv,
        current_profile_id=context.profile_id,
    )
    tray.setup()

    timer.start()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
