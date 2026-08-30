#!/usr/bin/env python3
"""Diagnose Linux input-method issues affecting Qt/PyQt applications.

This script is intended for troubleshooting cases where a user cannot switch
or use Chinese input methods on CentOS-like Linux environments. It performs
non-invasive checks and prints suggested remediation steps without changing
runtime behavior.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable


def _run(cmd: list[str]) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except FileNotFoundError:
        return 127, "", "command not found"


def _fmt_flag(name: str) -> str:
    value = os.environ.get(name)
    return value if value else "(unset)"


def _list_present(commands: Iterable[str]) -> list[str]:
    present: list[str] = []
    for cmd in commands:
        if shutil.which(cmd):
            present.append(cmd)
    return present


def _qt_plugin_dirs() -> list[Path]:
    candidates: list[Path] = []
    for env_name in ("QT_PLUGIN_PATH", "QT6_PLUGIN_PATH", "QT_PLUGIN_PATH_6"):
        if os.environ.get(env_name):
            for part in os.environ.get(env_name, "").split(os.pathsep):
                if part:
                    candidates.append(Path(part))

    if sys.platform.startswith("linux"):
        common_roots = [
            Path("/usr/lib64"),
            Path("/usr/lib"),
            Path("/usr/local/lib64"),
            Path("/usr/local/lib"),
        ]
        for root in common_roots:
            candidates.extend([
                root / "qt6/plugins",
                root / "qt5/plugins",
                root / "plugins",
            ])

    try:
        from PyQt6.QtCore import QLibraryInfo

        plugin_dir = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath))
        if plugin_dir.exists():
            candidates.append(plugin_dir)
    except Exception:
        pass

    uniq: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        try:
            key = str(path.resolve())
        except Exception:
            key = str(path)
        if key not in seen:
            seen.add(key)
            uniq.append(path)
    return uniq


def _print_section(title: str) -> None:
    print(f"\n=== {title} ===")


def main() -> int:
    print("POMATO Linux IME Diagnostic")
    print("Purpose: identify why an input method cannot switch to Chinese on Linux/Qt environment")
    print(f"Platform: {sys.platform}")
    print(f"Python: {sys.version.split()[0]}")
    print(f"Kernel: {platform_meta() if False else ''}")

    if not sys.platform.startswith("linux"):
        print("\nNot a Linux runtime. This diagnostic is intended for CentOS/fedora/Ubuntu-style systems.")
        return 0

    _print_section("Environment")
    for key in [
        "XDG_SESSION_TYPE",
        "DESKTOP_SESSION",
        "DISPLAY",
        "WAYLAND_DISPLAY",
        "LANG",
        "LC_ALL",
        "QT_IM_MODULE",
        "XMODIFIERS",
        "GTK_IM_MODULE",
        "QT_QPA_PLATFORM",
    ]:
        print(f"{key}={_fmt_flag(key)}")

    _print_section("Installed IM frameworks")
    known = ["ibus", "fcitx", "fcitx5", "xim", "zhcon"]
    for name in known:
        print(f"{name}: {'present' if shutil.which(name) else 'missing'}")

    _print_section("Common desktop-session tools")
    for cmd in ["ibus-daemon", "fcitx5", "fcitx", "dbus-launch", "xinput", "qtpaths6", "qtpaths"]:
        print(f"{cmd}: {'present' if shutil.which(cmd) else 'missing'}")

    _print_section("Qt plugin directories")
    plugin_dirs = _qt_plugin_dirs()
    if not plugin_dirs:
        print("No Qt plugin directories detected")
    else:
        for path in plugin_dirs:
            exists = "exists" if path.exists() else "missing"
            print(f"- {path} [{exists}]")
            if path.exists():
                for entry in ("xcb", "wayland"):
                    p = path / entry
                    print(f"  {entry}: {'present' if p.exists() else 'missing'}")

    _print_section("X11 / Wayland probes")
    code, out, err = _run(["bash", "-lc", "echo ${XDG_SESSION_TYPE:-unknown}; echo ${DISPLAY:-unset}; echo ${WAYLAND_DISPLAY:-unset}"])
    if code == 0:
        print(out)
    else:
        print(f"probe failed: {err or 'unknown error'}")

    _print_section("PyQt check")
    try:
        from PyQt6.QtCore import QLibraryInfo

        print(f"PyQt6 version: {__import__('PyQt6').QtCore.PYQT_VERSION_STR}")
        print(f"Qt version: {QLibraryInfo.version().toString()}")
        for name in [
            "PluginsPath",
            "LibrariesPath",
            "PrefixPath",
        ]:
            enum_member = getattr(QLibraryInfo, name, None)
            if enum_member is not None:
                print(f"{name}: {QLibraryInfo.path(enum_member)}")
    except Exception as exc:  # pragma: no cover - diagnostic only
        print(f"PyQt6 not importable or not configured: {exc}")

    _print_section("Risk summary")
    risks: list[str] = []
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        risks.append("No active graphical display is set; input method will not attach normally.")
    if not os.environ.get("QT_IM_MODULE"):
        risks.append("QT_IM_MODULE is unset; Qt may not activate the correct IME backend.")
    if not os.environ.get("XMODIFIERS") and os.environ.get("DISPLAY"):
        risks.append("XMODIFIERS is unset; classic X11 IM bridging may fail on CentOS/X11 desktops.")
    if not _list_present(["ibus", "fcitx", "fcitx5"]):
        risks.append("No common IME backend is installed in PATH; Chinese input may be unavailable.")
    if not risks:
        print("No obvious environment-level risk detected from the current shell.")
    else:
        for item in risks:
            print(f"- {item}")

    _print_section("Recommended next steps")
    print("1. Confirm the active Linux desktop is X11 or Wayland and matches the IME backend.")
    print("2. Try launching the app with one of these environment overrides:")
    print("   QT_IM_MODULE=fcitx5 XMODIFIERS=@im=fcitx5 <app-command>")
    print("   or")
    print("   QT_IM_MODULE=ibus XMODIFIERS=@im=ibus <app-command>")
    print("3. Ensure ibus/fcitx5 packages are installed and the corresponding daemon is running.")
    print("4. If using Wayland, validate that the desktop session provides IME support for Qt apps.")
    print("5. Re-run this script in the same session where the app is launched to compare environment variables.")

    return 0


def platform_meta() -> str:
    return f"{os.uname().sysname} {os.uname().release} {os.uname().machine}" if hasattr(os, "uname") else platform_name()


def platform_name() -> str:
    return sys.platform


if __name__ == "__main__":
    raise SystemExit(main())
