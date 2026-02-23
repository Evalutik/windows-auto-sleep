"""
test_password.py — Unit tests for core/password.py.

All tests redirect storage to a temporary directory so the real
%LOCALAPPDATA%\\WindowsCfgSvc path is never touched.
NTFS icacls calls are mocked so the tests run on any user account.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

import core.password as pwd_mod


# ── Fixtures ───────────────────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def tmp_storage(tmp_path: Path) -> None:
    """Redirect password storage to a pytest tmp directory before each test."""
    app_dir    = tmp_path / "WindowsCfgSvc"
    passwd_file = app_dir / "cfg.dat"
    pwd_mod._override_paths(app_dir, passwd_file)
    yield
    # Override persists only for this test; next test gets its own tmp_path


@pytest.fixture(autouse=True)
def mock_icacls(monkeypatch: pytest.MonkeyPatch) -> None:
    """Suppress real icacls calls (NTFS ACL changes) during tests."""
    monkeypatch.setattr(
        subprocess, "run",
        lambda *a, **kw: subprocess.CompletedProcess(a, 0),
    )


# ── has_password ───────────────────────────────────────────────────────────
class TestHasPassword:
    def test_false_when_no_file(self) -> None:
        assert not pwd_mod.has_password()

    def test_true_after_set(self) -> None:
        pwd_mod.set_password("secret")
        assert pwd_mod.has_password()


# ── set_password / verify_password ────────────────────────────────────────
class TestSetAndVerify:
    def test_correct_password_returns_true(self) -> None:
        pwd_mod.set_password("correcthorsebatterystaple")
        assert pwd_mod.verify_password("correcthorsebatterystaple")

    def test_wrong_password_returns_false(self) -> None:
        pwd_mod.set_password("correcthorsebatterystaple")
        assert not pwd_mod.verify_password("wrongpassword")

    def test_empty_password_round_trip(self) -> None:
        """An empty string is a valid password (though discouraged)."""
        pwd_mod.set_password("")
        assert pwd_mod.verify_password("")
        assert not pwd_mod.verify_password("notempty")

    def test_unicode_password(self) -> None:
        pwd_mod.set_password("пароль🔒")
        assert pwd_mod.verify_password("пароль🔒")
        assert not pwd_mod.verify_password("pароль🔒")  # Cyrillic 'п' replaced

    def test_no_password_always_allows(self) -> None:
        """If no password is stored, verify should return True (no restriction)."""
        assert not pwd_mod.has_password()
        assert pwd_mod.verify_password("anything")

    def test_verify_handles_corrupt_file(self, tmp_path: Path) -> None:
        """If the file is corrupt, verify should return False (fail safe)."""
        pwd_mod._PASSWD_FILE.parent.mkdir(parents=True, exist_ok=True)
        pwd_mod._PASSWD_FILE.write_bytes(b"not_a_valid_bcrypt_hash")
        assert not pwd_mod.verify_password("anything")


# ── delete_password ────────────────────────────────────────────────────────
class TestDeletePassword:
    def test_delete_removes_file(self) -> None:
        pwd_mod.set_password("bye")
        assert pwd_mod.has_password()
        pwd_mod.delete_password()
        assert not pwd_mod.has_password()

    def test_delete_noop_if_no_file(self) -> None:
        pwd_mod.delete_password()   # must not raise


# ── uninstall_app_data ────────────────────────────────────────────────────
class TestUninstall:
    def test_removes_file_and_dir(self) -> None:
        pwd_mod.set_password("x")
        assert pwd_mod._APP_DIR.exists()
        pwd_mod.uninstall_app_data()
        assert not pwd_mod._PASSWD_FILE.exists()
        assert not pwd_mod._APP_DIR.exists()

    def test_noop_if_never_set(self) -> None:
        pwd_mod.uninstall_app_data()   # must not raise
