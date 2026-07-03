import subprocess
import sys
from pathlib import Path


def build_restart_command(program_args: list[str] | None = None) -> list[str]:
    args = list(program_args) if program_args is not None else list(sys.argv[1:])
    if getattr(sys, "frozen", False):
        return [sys.executable, *args]

    script_path = Path(sys.argv[0])
    return [sys.executable, str(script_path), *args]


def restart_application(program_args: list[str] | None = None):
    command = build_restart_command(program_args)
    subprocess.Popen(command)
