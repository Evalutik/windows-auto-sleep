"""
main.py — Entry point for windows-auto-sleep.

Flow
----
1. Check if the first instance's mutex exists (via ipc.is_first_instance_running).

SECOND INSTANCE (timer already running)
  a. If a password is set → show DeactivationWindow (asks for password).
  b. Send cancel signal via IPC (signal_cancel).
  c. Wait for the first instance's ACK.
  d. Show success / wrong-password / timeout result.

FIRST INSTANCE (no timer running)
  a. Show ActivationWindow (set duration/time + optional password).
  b. On "Activate":
       – Store password (if entered) via password.set_password().
       – Create IPC server objects (mutex + events).
       – Start ShutdownScheduler.
       – Start SleepTray icon.
       – Begin monitoring the cancel event in a daemon thread.
  c. When cancel signal arrives:
       – Read password from temp file.
       – Verify it.
       – If correct: cancel scheduler, send ACK, stop tray, quit.
       – If wrong: reset events, keep running.
  d. When the timer fires naturally: stop tray, execute shutdown.
  e. On "Uninstall": call password.uninstall_app_data(), show message, quit.
"""
from __future__ import annotations

import ctypes
import sys
import os
import threading
import tkinter as tk
from tkinter import messagebox

from core import ipc, password, scheduler, shutdown
from gui.activation_window import ActivationWindow
from gui.deactivation_window import DeactivationWindow
from gui.tray import SleepTray


# ── Admin elevation ────────────────────────────────────────────────────────
def _pythonw_exe() -> str:
    """Return path to pythonw.exe next to the current python.exe."""
    import os as _os
    return _os.path.join(_os.path.dirname(sys.executable), "pythonw.exe")


def _ensure_admin() -> None:
    """If the process is not elevated, re-launch elevated (no console) and exit."""
    try:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        is_admin = False

    if not is_admin:
        frozen = getattr(sys, "frozen", False)
        if frozen:
            exe  = sys.executable
            args = ""
        else:
            # Use pythonw.exe so the elevated copy has NO console window
            exe  = _pythonw_exe()
            args = f'"{os.path.abspath(__file__)}"'
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", exe, args, None, 1,
        )
        sys.exit(0)




# ── Module-level state (first instance only) ───────────────────────────────
_sched: scheduler.ShutdownScheduler | None = None
_tray:  SleepTray | None = None


# ══════════════════════════════════════════════════════════════════════════
# SECOND-INSTANCE path
# ══════════════════════════════════════════════════════════════════════════
def run_deactivation() -> None:
    needs_pw = password.has_password()

    def on_submit(pw: str) -> str:
        """Called from a background thread inside DeactivationWindow.
        Sends the cancel signal and waits for ACK or NACK from the first instance.
        Returns 'ack', 'nack', or 'timeout'.
        """
        ipc.signal_cancel(pw)
        return ipc.wait_for_response(timeout_ms=5000)

    win = DeactivationWindow(needs_password=needs_pw, on_submit=on_submit)
    win.run()


# ══════════════════════════════════════════════════════════════════════════
# FIRST-INSTANCE path
# ══════════════════════════════════════════════════════════════════════════
def _cancel_monitor() -> None:
    """Daemon thread: waits for a cancel signal, verifies password, acts."""
    global _sched, _tray

    while True:
        signalled = ipc.wait_for_cancel(timeout_ms=500)
        if not signalled:
            # Check if scheduler is still active (it may have just fired)
            if _sched is not None and not _sched.is_active:
                break
            continue

        # Cancel signal received
        entered = ipc.read_cancel_password()
        if password.verify_password(entered):
            # ── Correct password (or no password set) ──────────────────────
            if _sched is not None:
                _sched.cancel()
            ipc.send_ack()
            ipc.destroy_server_objects()
            password.delete_password()  # Cleanup: password is one-time use
            if _tray is not None:
                _tray.stop()
            break
        else:
            # ── Wrong password — signal NACK instantly, keep running ────────
            ipc.send_nack()
            ipc.reset_for_next_attempt()


def _on_timer_fired() -> None:
    """Called by the scheduler thread when time is up — execute shutdown."""
    global _tray
    ipc.destroy_server_objects()
    if _tray is not None:
        _tray.stop()
    password.delete_password()  # Ensure no password file is left after shutdown
    shutdown.execute_shutdown()


def run_activation() -> None:
    global _sched, _tray

    # Cleanup stale password file if no timer is running (prevent leftovers)
    if password.has_password():
        password.delete_password()

    activated: dict = {}   # filled by on_activate callback

    def on_activate(minutes: float, pw: str) -> None:
        activated["minutes"] = minutes
        activated["password"] = pw

    def on_uninstall() -> None:
        password.uninstall_app_data()
        _show_simple_message(
            "Uninstall complete",
            "All app data has been removed.\n"
            "You can now safely delete the exe file.",
        )

    win = ActivationWindow(on_activate=on_activate, on_uninstall=on_uninstall)
    win.run()   # blocks until Activate clicked or window closed

    if "minutes" not in activated:
        # User closed window without activating → just quit
        return

    minutes = activated["minutes"]
    pw      = activated["password"]

    # Store password (skip if none entered)
    if pw:
        password.set_password(pw)

    # Set up IPC objects
    ipc.create_server_objects()

    # Start scheduler
    _sched = scheduler.ShutdownScheduler(callback=_on_timer_fired)
    _sched.schedule_duration(minutes=minutes)

    # Start tray
    _tray = SleepTray()
    _tray.start()

    # Start cancel monitor daemon thread
    monitor = threading.Thread(target=_cancel_monitor, daemon=True, name="cancel-monitor")
    monitor.start()

    # Keep main thread alive (tray + monitor run as daemons)
    monitor.join()


# ══════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════
def _show_simple_message(title: str, msg: str) -> None:
    root = tk.Tk()
    root.withdraw()
    messagebox.showinfo(title, msg)
    root.destroy()


# ══════════════════════════════════════════════════════════════════════════
# Entry
# ══════════════════════════════════════════════════════════════════════════
def main() -> None:
    if ipc.is_first_instance_running():
        # Second instance: cancel the running timer.
        # No admin needed — we're just sending a signal, not shutting down.
        run_deactivation()
    else:
        # First instance: we are the shutdown process — must be elevated.
        _ensure_admin()
        run_activation()


if __name__ == "__main__":
    main()
