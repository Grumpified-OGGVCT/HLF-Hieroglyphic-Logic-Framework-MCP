"""HLF stdlib: system module."""

import os
import platform
import sys
import time


def SYS_OS() -> str:
    return platform.system()


def SYS_ARCH() -> str:
    return platform.machine()


def SYS_CWD() -> str:
    return os.getcwd()


def SYS_ENV(var: str) -> str:
    return os.environ.get(var, "")


def SYS_SETENV(var: str, value: str) -> bool:
    os.environ[var] = value
    return True


def SYS_TIME() -> int:
    return int(time.time())


def SYS_SLEEP(ms: int) -> bool:
    time.sleep(ms / 1000)
    return True


def SYS_EXIT(code: int) -> None:
    sys.exit(code)


def SYS_EXEC(cmd: str, args: list[str] | None = None) -> str:
    import subprocess

    result = subprocess.run([cmd] + (args or []), capture_output=True, text=True, timeout=30)
    return result.stdout
