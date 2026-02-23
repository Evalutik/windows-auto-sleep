"""
password.py — Secure password storage using bcrypt + NTFS deny-delete ACL.

Layout
------
  %LOCALAPPDATA%\\WindowsCfgSvc\\cfg.dat   ← bcrypt hash (binary)

After writing, an NTFS "deny delete" ACE is applied to cfg.dat so that even
an Admin user cannot delete it through Explorer or a simple script — they
would first have to reset the ACL.  Reading the file does NOT require
removing the ACL, so verification works without changing permissions.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional

import bcrypt

# ── Storage location (disguised under a system-sounding name) ─────────────
_APP_DIR    = Path(os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))) / "WindowsCfgSvc"
_PASSWD_FILE = _APP_DIR / "cfg.dat"


# ── Internal helpers ───────────────────────────────────────────────────────
def _ensure_dir() -> None:
    _APP_DIR.mkdir(parents=True, exist_ok=True)


def _apply_deny_delete(path: Path) -> None:
    """Add a deny-delete ACE for Everyone on *path* via icacls."""
    subprocess.run(
        ["icacls", str(path), "/deny", "Everyone:(D)"],
        capture_output=True,
        check=False,
    )


def _remove_deny_delete(path: Path) -> None:
    """Remove all custom ACEs and restore inherited permissions via icacls."""
    subprocess.run(
        ["icacls", str(path), "/reset"],
        capture_output=True,
        check=False,
    )


# ── Public API ─────────────────────────────────────────────────────────────
def set_password(plain: str) -> None:
    """Hash *plain* with bcrypt and write it to storage, then lock the file."""
    _ensure_dir()
    hashed: bytes = bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt())
    _PASSWD_FILE.write_bytes(hashed)
    _apply_deny_delete(_PASSWD_FILE)


def verify_password(plain: str) -> bool:
    """Return True if *plain* matches the stored hash, or if no password is set."""
    if not has_password():
        return True          # no password configured → always allow cancel
    try:
        stored = _PASSWD_FILE.read_bytes()
        return bcrypt.checkpw(plain.encode("utf-8"), stored)
    except Exception:
        return False


def has_password() -> bool:
    """Return True if a password file exists in storage."""
    return _PASSWD_FILE.exists()


def delete_password() -> None:
    """Remove the password file (resets ACL first so deletion is possible)."""
    if _PASSWD_FILE.exists():
        _remove_deny_delete(_PASSWD_FILE)
        try:
            _PASSWD_FILE.unlink()
        except PermissionError:
            # icacls /reset sometimes needs a moment; retry once
            _PASSWD_FILE.unlink(missing_ok=True)


def uninstall_app_data() -> None:
    """Delete all app data (password file + directory).

    Called from the UI's "Uninstall" button when no timer is active.
    """
    delete_password()
    try:
        _APP_DIR.rmdir()   # succeeds only if directory is now empty
    except Exception:
        pass


# ── Test-friendly path overrides ───────────────────────────────────────────
def _override_paths(app_dir: Path, passwd_file: Path) -> None:  # pragma: no cover – test helper
    """Redirect storage to a temp directory during unit tests."""
    global _APP_DIR, _PASSWD_FILE
    _APP_DIR     = app_dir
    _PASSWD_FILE = passwd_file
