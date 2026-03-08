"""
ipc.py — Inter-process communication via Windows Named Objects.

Mechanism
---------
First instance (server)
  • Creates Named Mutex  ``Local\\AutoSleepRunning``  — signals "timer is active"
  • Creates Named Event  ``Local\\AutoSleepCancel``   — second instance sets this to request cancel
  • Creates Named Event  ``Local\\AutoSleepAck``      — first instance sets on correct password
  • Creates Named Event  ``Local\\AutoSleepNack``     — first instance sets on wrong password

Cancel protocol
  1. Second instance writes password to temp file, sets cancel event.
  2. First instance wakes, verifies password.
     - Correct → send_ack()  → timer cancelled.
     - Wrong   → send_nack() → second instance retries.
  3. Second instance calls wait_for_response() which returns 'ack', 'nack', or 'timeout'.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Optional

import win32api
import win32event
import win32con
import win32security
import pywintypes
import winerror

# ── Named-object names ─────────────────────────────────────────────────────
_MUTEX_NAME  = "Local\\AutoSleepRunning"
_CANCEL_NAME = "Local\\AutoSleepCancel"
_ACK_NAME    = "Local\\AutoSleepAck"
_NACK_NAME   = "Local\\AutoSleepNack"

# Temp file used to pass the plain-text password from client → server
_TEMP_REQUEST = Path(tempfile.gettempdir()) / "as_req.tmp"

# Module-level handles held by the first instance
_mutex_handle:  Optional[object] = None
_cancel_handle: Optional[object] = None
_ack_handle:    Optional[object] = None
_nack_handle:   Optional[object] = None


def _get_null_sa() -> win32security.SECURITY_ATTRIBUTES:
    """Return SECURITY_ATTRIBUTES with a NULL DACL allowing everyone access."""
    sd = win32security.SECURITY_DESCRIPTOR()
    sd.SetSecurityDescriptorDacl(1, None, 0)
    sa = win32security.SECURITY_ATTRIBUTES()
    sa.SECURITY_DESCRIPTOR = sd
    return sa


# ── First-instance (server) side ───────────────────────────────────────────
def create_server_objects() -> None:
    """Create the named mutex and events. Called once by the first instance."""
    global _mutex_handle, _cancel_handle, _ack_handle, _nack_handle
    sa = _get_null_sa()
    _mutex_handle  = win32event.CreateMutex(sa, True, _MUTEX_NAME)
    # Auto-reset events (bManualReset=False) prevent race conditions
    _cancel_handle = win32event.CreateEvent(sa, False, False, _CANCEL_NAME)
    _ack_handle    = win32event.CreateEvent(sa, False, False, _ACK_NAME)
    _nack_handle   = win32event.CreateEvent(sa, False, False, _NACK_NAME)


def destroy_server_objects() -> None:
    """Release all named objects."""
    global _mutex_handle, _cancel_handle, _ack_handle, _nack_handle
    for h in (_mutex_handle, _cancel_handle, _ack_handle, _nack_handle):
        if h is not None:
            try:
                win32api.CloseHandle(h)
            except Exception:
                pass
    _mutex_handle = _cancel_handle = _ack_handle = _nack_handle = None


def wait_for_cancel(timeout_ms: int = win32event.INFINITE) -> bool:
    """Block until the cancel event is signalled. Returns True if signalled."""
    if _cancel_handle is None:
        return False
    result = win32event.WaitForSingleObject(_cancel_handle, timeout_ms)
    return result == win32event.WAIT_OBJECT_0


def read_cancel_password() -> str:
    """Read the plain-text password left by the second instance, then delete the file."""
    try:
        text = _TEMP_REQUEST.read_text(encoding="utf-8")
        _TEMP_REQUEST.unlink(missing_ok=True)
        return text
    except Exception:
        return ""


def send_ack() -> None:
    """Signal success — correct password, timer will be cancelled."""
    if _ack_handle is not None:
        win32event.SetEvent(_ack_handle)


def send_nack() -> None:
    """Signal failure — wrong password, timer keeps running."""
    if _nack_handle is not None:
        win32event.SetEvent(_nack_handle)


def reset_for_next_attempt() -> None:
    """No-op. Left for backwards compatibility, auto-reset handles state."""
    pass


# ── Second-instance (client) side ─────────────────────────────────────────
def is_first_instance_running() -> bool:
    """Return True if the first instance's mutex is present."""
    try:
        h = win32event.OpenMutex(win32con.SYNCHRONIZE, False, _MUTEX_NAME)
        win32api.CloseHandle(h)
        return True
    except pywintypes.error as e:
        if getattr(e, 'winerror', None) == winerror.ERROR_ACCESS_DENIED:
            return True
        return False


def send_cancel_and_wait(password: str, timeout_ms: int = 5000) -> str:
    """Safely open response handles, signal cancel, and wait for response.
    
    Opens ACK/NACK handles before signaling CANCEL to ensure the handles are 
    held open, preventing the server from destroying them before we can wait.
    """
    try:
        ack_h  = win32event.OpenEvent(win32con.SYNCHRONIZE, False, _ACK_NAME)
        nack_h = win32event.OpenEvent(win32con.SYNCHRONIZE, False, _NACK_NAME)
    except pywintypes.error:
        return "timeout"

    _TEMP_REQUEST.write_text(password, encoding="utf-8")
    
    try:
        cancel_h = win32event.OpenEvent(win32con.EVENT_MODIFY_STATE, False, _CANCEL_NAME)
        win32event.SetEvent(cancel_h)
        win32api.CloseHandle(cancel_h)
    except pywintypes.error:
        win32api.CloseHandle(ack_h)
        win32api.CloseHandle(nack_h)
        return "timeout"
        
    try:
        result = win32event.WaitForMultipleObjects([ack_h, nack_h], False, timeout_ms)
        if result == win32event.WAIT_OBJECT_0:
            return "ack"
        elif result == win32event.WAIT_OBJECT_0 + 1:
            return "nack"
        else:
            return "timeout"
    except pywintypes.error:
        return "timeout"
    finally:
        win32api.CloseHandle(ack_h)
        win32api.CloseHandle(nack_h)
