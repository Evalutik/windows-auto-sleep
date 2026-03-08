"""
shutdown.py — Forced Windows power-off.

Using subprocess to call the built-in Windows shutdown executable is far more
reliable than manipulating process tokens and calling ExitWindowsEx via ctypes,
especially on newer Windows versions where the API might fail silently.
"""
from __future__ import annotations

import subprocess
from typing import Callable, Optional


def execute_shutdown(_override: Optional[Callable[[], None]] = None) -> None:
    """Perform a forced system poweroff.

    Args:
        _override: If provided, call this instead of the real Windows API.
                   Used exclusively in unit tests — never pass this in
                   production code.
    """
    if _override is not None:
        _override()
        return

    # Use shutdown.exe to reliably shut down, avoiding brittle token manipulation.
    # /s = shutdown, /f = force apps to close, /t 0 = immediately.
    # CREATE_NO_WINDOW prevents a console flash.
    subprocess.run(
        ["shutdown", "/s", "/f", "/t", "0"],
        creationflags=subprocess.CREATE_NO_WINDOW,
        check=False
    )


def execute_lock(_override: Optional[Callable[[], None]] = None) -> None:
    """Perform a workstation lock (log out to lock screen).

    Args:
        _override: If provided, call this instead of the real Windows API.
                   Used exclusively in unit tests.
    """
    if _override is not None:
        _override()
        return

    subprocess.run(
        ["rundll32.exe", "user32.dll,LockWorkStation"],
        creationflags=subprocess.CREATE_NO_WINDOW,
        check=False
    )
