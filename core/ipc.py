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
import pywintypes

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


# ── First-instance (server) side ───────────────────────────────────────────
def create_server_objects() -> None:
    """Create the named mutex and events. Called once by the first instance."""
    global _mutex_handle, _cancel_handle, _ack_handle, _nack_handle
    _mutex_handle  = win32event.CreateMutex(None, True, _MUTEX_NAME)
    # Manual-reset events so we can reset them after each attempt
    _cancel_handle = win32event.CreateEvent(None, True, False, _CANCEL_NAME)
    _ack_handle    = win32event.CreateEvent(None, True, False, _ACK_NAME)
    _nack_handle   = win32event.CreateEvent(None, True, False, _NACK_NAME)


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
    """Reset cancel + nack events so the second instance can try again."""
    if _cancel_handle is not None:
        win32event.ResetEvent(_cancel_handle)
    if _nack_handle is not None:
        win32event.ResetEvent(_nack_handle)


# ── Second-instance (client) side ─────────────────────────────────────────
def is_first_instance_running() -> bool:
    """Return True if the first instance's mutex is present."""
    try:
        h = win32event.OpenMutex(win32con.SYNCHRONIZE, False, _MUTEX_NAME)
        win32api.CloseHandle(h)
        return True
    except pywintypes.error:
        return False


def signal_cancel(password: str) -> None:
    """Write the password to the temp file and fire the cancel event."""
    _TEMP_REQUEST.write_text(password, encoding="utf-8")
    try:
        h = win32event.OpenEvent(win32con.EVENT_MODIFY_STATE, False, _CANCEL_NAME)
        win32event.SetEvent(h)
        win32api.CloseHandle(h)
    except pywintypes.error:
        pass


def wait_for_response(timeout_ms: int = 5000) -> str:
    """Wait for ACK or NACK from the first instance.

    Returns:
        'ack'     — correct password, timer cancelled.
        'nack'    — wrong password, try again.
        'timeout' — no response (first instance may have already shut down).
    """
    try:
        ack_h  = win32event.OpenEvent(win32con.SYNCHRONIZE, False, _ACK_NAME)
        nack_h = win32event.OpenEvent(win32con.SYNCHRONIZE, False, _NACK_NAME)
        result = win32event.WaitForMultipleObjects([ack_h, nack_h], False, timeout_ms)
        win32api.CloseHandle(ack_h)
        win32api.CloseHandle(nack_h)
        if result == win32event.WAIT_OBJECT_0:
            return "ack"
        elif result == win32event.WAIT_OBJECT_0 + 1:
            return "nack"
        else:
            return "timeout"
    except pywintypes.error:
        return "timeout"
