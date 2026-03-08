"""
test_shutdown.py — Unit tests for core/shutdown.py.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch
import subprocess

import core.shutdown as sd


class TestExecuteShutdown:
    def test_calls_override_if_provided(self) -> None:
        called = []
        sd.execute_shutdown(_override=lambda: called.append(True))
        assert called == [True]

    def test_override_is_not_called_when_none(self) -> None:
        """When _override is None, subprocess.run is called."""
        with patch.object(subprocess, "run") as mock_run:
            sd.execute_shutdown()

        mock_run.assert_called_once_with(
            ["shutdown", "/s", "/f", "/t", "0"],
            creationflags=subprocess.CREATE_NO_WINDOW,
            check=False
        )

    def test_override_receives_no_arguments(self) -> None:
        """The override callable is called with zero arguments."""
        mock_fn = MagicMock()
        sd.execute_shutdown(_override=mock_fn)
        mock_fn.assert_called_once_with()


class TestExecuteLock:
    def test_calls_override_if_provided(self) -> None:
        called = []
        sd.execute_lock(_override=lambda: called.append(True))
        assert called == [True]

    def test_override_is_not_called_when_none(self) -> None:
        """When _override is None, subprocess.run is called."""
        with patch.object(subprocess, "run") as mock_run:
            sd.execute_lock()

        mock_run.assert_called_once_with(
            ["rundll32.exe", "user32.dll,LockWorkStation"],
            creationflags=subprocess.CREATE_NO_WINDOW,
            check=False
        )

    def test_override_receives_no_arguments(self) -> None:
        """The override callable is called with zero arguments."""
        mock_fn = MagicMock()
        sd.execute_lock(_override=mock_fn)
        mock_fn.assert_called_once_with()
