"""
shutdown.py — Forced Windows power-off via ExitWindowsEx.

The public surface is intentionally minimal so tests can inject a mock
callback instead of ever touching the real API.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as _wt
from typing import Callable, Optional

# ── Windows constants ──────────────────────────────────────────────────────
EWX_POWEROFF            = 0x00000008
EWX_FORCE               = 0x00000004
SE_PRIVILEGE_ENABLED    = 0x00000002
TOKEN_ADJUST_PRIVILEGES = 0x00000020
TOKEN_QUERY             = 0x00000008
SHTDN_REASON_FLAG_PLANNED = 0x80000000


# ── Internal structures ────────────────────────────────────────────────────
class _LUID(ctypes.Structure):
    _fields_ = [("LowPart", _wt.DWORD), ("HighPart", _wt.LONG)]


class _LUID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Luid", _LUID), ("Attributes", _wt.DWORD)]


class _TOKEN_PRIVILEGES(ctypes.Structure):
    _fields_ = [
        ("PrivilegeCount", _wt.DWORD),
        ("Privileges", _LUID_AND_ATTRIBUTES * 1),
    ]


# ── Privilege helper ───────────────────────────────────────────────────────
def request_shutdown_privilege() -> None:
    """Acquire SeShutdownPrivilege for the current process token.

    This is required before calling ExitWindowsEx. On standard Windows
    user accounts the privilege already exists in the token but must be
    *enabled* explicitly.
    """
    advapi32 = ctypes.windll.advapi32
    kernel32 = ctypes.windll.kernel32

    h_token = _wt.HANDLE()
    advapi32.OpenProcessToken(
        kernel32.GetCurrentProcess(),
        TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY,
        ctypes.byref(h_token),
    )

    luid = _LUID()
    advapi32.LookupPrivilegeValueW(None, "SeShutdownPrivilege", ctypes.byref(luid))

    tp = _TOKEN_PRIVILEGES()
    tp.PrivilegeCount = 1
    tp.Privileges[0].Luid = luid
    tp.Privileges[0].Attributes = SE_PRIVILEGE_ENABLED

    advapi32.AdjustTokenPrivileges(h_token, False, ctypes.byref(tp), 0, None, None)
    kernel32.CloseHandle(h_token)


# ── Public API ─────────────────────────────────────────────────────────────
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

    request_shutdown_privilege()
    ctypes.windll.user32.ExitWindowsEx(
        EWX_POWEROFF | EWX_FORCE,
        SHTDN_REASON_FLAG_PLANNED,
    )
