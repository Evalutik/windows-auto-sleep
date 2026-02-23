"""
test_ipc.py — Unit tests for core/ipc.py.

All Win32 handle operations are mocked with simple fakes so the tests
run without touching real named kernel objects (which would require certain
Windows privileges and could interfere with a real running instance).
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest


# ── Fake win32event constants / functions ──────────────────────────────────
WAIT_OBJECT_0 = 0
WAIT_TIMEOUT  = 258
INFINITE      = 0xFFFFFFFF

_fake_win32event = MagicMock()
_fake_win32event.WAIT_OBJECT_0 = WAIT_OBJECT_0
_fake_win32event.WAIT_TIMEOUT  = WAIT_TIMEOUT
_fake_win32event.INFINITE      = INFINITE

_fake_win32con = MagicMock()
_fake_win32con.SYNCHRONIZE        = 0x00100000
_fake_win32con.EVENT_MODIFY_STATE = 0x0002

import sys
sys.modules.setdefault("win32event", _fake_win32event)
sys.modules.setdefault("win32con",   _fake_win32con)
sys.modules.setdefault("pywintypes", MagicMock())

import core.ipc as ipc_mod   # noqa: E402 — import after mocks are inserted


# ── Fixture: redirect temp request file to pytest tmp ─────────────────────
@pytest.fixture(autouse=True)
def patch_temp_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ipc_mod, "_TEMP_REQUEST", tmp_path / "as_req.tmp")


@pytest.fixture(autouse=True)
def reset_handles(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reset module-level handles before each test."""
    monkeypatch.setattr(ipc_mod, "_mutex_handle",  None)
    monkeypatch.setattr(ipc_mod, "_cancel_handle", None)
    monkeypatch.setattr(ipc_mod, "_ack_handle",    None)


# ── create_server_objects ──────────────────────────────────────────────────
class TestCreateServerObjects:
    def test_creates_three_objects(self) -> None:
        _fake_win32event.CreateMutex.return_value  = MagicMock(name="mutex")
        _fake_win32event.CreateEvent.return_value  = MagicMock(name="event")
        ipc_mod.create_server_objects()
        assert _fake_win32event.CreateMutex.called
        assert _fake_win32event.CreateEvent.call_count >= 2


# ── destroy_server_objects ─────────────────────────────────────────────────
class TestDestroyServerObjects:
    def test_closes_all_handles(self) -> None:
        h1, h2, h3 = MagicMock(), MagicMock(), MagicMock()
        ipc_mod._mutex_handle  = h1
        ipc_mod._cancel_handle = h2
        ipc_mod._ack_handle    = h3
        ipc_mod.destroy_server_objects()
        assert _fake_win32event.CloseHandle.call_count >= 3

    def test_noop_if_no_handles(self) -> None:
        ipc_mod.destroy_server_objects()  # should not raise


# ── wait_for_cancel ────────────────────────────────────────────────────────
class TestWaitForCancel:
    def test_returns_true_on_signal(self) -> None:
        ipc_mod._cancel_handle = MagicMock()
        _fake_win32event.WaitForSingleObject.return_value = WAIT_OBJECT_0
        assert ipc_mod.wait_for_cancel(timeout_ms=100) is True

    def test_returns_false_on_timeout(self) -> None:
        ipc_mod._cancel_handle = MagicMock()
        _fake_win32event.WaitForSingleObject.return_value = WAIT_TIMEOUT
        assert ipc_mod.wait_for_cancel(timeout_ms=100) is False

    def test_returns_false_if_no_handle(self) -> None:
        assert ipc_mod.wait_for_cancel(timeout_ms=100) is False


# ── read_cancel_password / signal_cancel ──────────────────────────────────
class TestTempFile:
    def test_signal_then_read(self, tmp_path: Path) -> None:
        req_file = tmp_path / "as_req.tmp"
        ipc_mod._TEMP_REQUEST = req_file
        # Suppress actual event open in signal_cancel
        _fake_win32event.OpenEvent.return_value = MagicMock()
        ipc_mod.signal_cancel("mypassword")
        assert req_file.exists()
        result = ipc_mod.read_cancel_password()
        assert result == "mypassword"
        assert not req_file.exists()   # file deleted after read

    def test_read_returns_empty_if_no_file(self, tmp_path: Path) -> None:
        req_file = tmp_path / "does_not_exist.tmp"
        ipc_mod._TEMP_REQUEST = req_file
        assert ipc_mod.read_cancel_password() == ""


# ── is_first_instance_running ─────────────────────────────────────────────
class TestIsFirstInstanceRunning:
    def test_true_when_mutex_opens(self) -> None:
        _fake_win32event.OpenMutex.return_value = MagicMock()
        # Reset side_effect so it does NOT raise
        _fake_win32event.OpenMutex.side_effect = None
        assert ipc_mod.is_first_instance_running() is True

    def test_false_when_mutex_missing(self) -> None:
        import pywintypes as _pywt
        _pywt.error = type("error", (Exception,), {})
        _fake_win32event.OpenMutex.side_effect = _pywt.error("not found")
        assert ipc_mod.is_first_instance_running() is False
        _fake_win32event.OpenMutex.side_effect = None   # reset
