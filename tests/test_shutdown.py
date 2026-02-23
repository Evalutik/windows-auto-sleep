"""
test_shutdown.py — Unit tests for core/shutdown.py.

The real ExitWindowsEx / AdjustTokenPrivileges calls are NEVER made.
We only test:
  1. That execute_shutdown calls the _override if provided.
  2. That execute_shutdown calls request_shutdown_privilege + ExitWindowsEx
     when no override is provided (mocked via monkeypatch on ctypes.windll).
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch, call
import ctypes

import pytest

import core.shutdown as sd


class TestExecuteShutdown:
    def test_calls_override_if_provided(self) -> None:
        called = []
        sd.execute_shutdown(_override=lambda: called.append(True))
        assert called == [True]

    def test_override_is_not_called_when_none(self) -> None:
        """When _override is None the real path is taken (mocked below)."""
        fake_user32   = MagicMock()
        fake_advapi32 = MagicMock()
        fake_kernel32 = MagicMock()
        # Make OpenProcessToken succeed and return a handle value
        fake_kernel32.GetCurrentProcess.return_value = 0xDEAD

        with patch.object(ctypes.windll, "user32",   fake_user32,   create=True), \
             patch.object(ctypes.windll, "advapi32", fake_advapi32, create=True), \
             patch.object(ctypes.windll, "kernel32", fake_kernel32, create=True):
            sd.execute_shutdown()   # must NOT raise

        fake_user32.ExitWindowsEx.assert_called_once_with(
            sd.EWX_POWEROFF | sd.EWX_FORCE,
            sd.SHTDN_REASON_FLAG_PLANNED,
        )

    def test_override_receives_no_arguments(self) -> None:
        """The override callable is called with zero arguments."""
        mock_fn = MagicMock()
        sd.execute_shutdown(_override=mock_fn)
        mock_fn.assert_called_once_with()


class TestRequestShutdownPrivilege:
    def test_runs_without_error_when_mocked(self) -> None:
        """Exercise the privilege-adjustment code path with mocked Win32 calls."""
        fake_advapi32 = MagicMock()
        fake_kernel32 = MagicMock()
        fake_kernel32.GetCurrentProcess.return_value = 0x1234

        with patch.object(ctypes.windll, "advapi32", fake_advapi32, create=True), \
             patch.object(ctypes.windll, "kernel32", fake_kernel32, create=True):
            sd.request_shutdown_privilege()   # must NOT raise

        assert fake_advapi32.OpenProcessToken.called
        assert fake_advapi32.LookupPrivilegeValueW.called
        assert fake_advapi32.AdjustTokenPrivileges.called
