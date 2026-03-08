"""
deactivation_window.py — Password dialog shown by the second instance.

The window stays open through the entire check:
  - While checking  → shows "Checking…" and disables the button
  - Wrong password  → shows inline error, re-enables for retry (no close)
  - Success         → shows green "Cancelled!" inline, auto-closes after 2s
  - Timeout         → shows inline warning, auto-closes after 3s

on_submit(password: str) -> str
    Called in a background thread.
    Must return 'ack', 'nack', or 'timeout'.
"""
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk
from typing import Callable

from gui import get_icon_path

# ── Palette ────────────────────────────────────────────────────────────────
_BG     = "#313338"   # dark discord background
_FG     = "#dbdee1"   # text
_ACCENT = "#5865F2"   # blurple accent
_ENTRY  = "#1e1f22"   # entry background
_RED    = "#da373c"   # error / destructive
_GREEN  = "#57f287"   # success
_YELLOW = "#fee75c"   # warning


class DeactivationWindow:
    def __init__(
        self,
        needs_password: bool,
        on_submit: Callable[[str], str],   # returns 'ack' | 'nack' | 'timeout'
    ) -> None:
        self._needs_password = needs_password
        self._on_submit      = on_submit

        self._root = tk.Tk()
        self._root.title("Sleep Timer — Cancel")
        self._root.resizable(False, False)
        self._root.configure(bg=_BG)
        self._root.attributes("-topmost", True)
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

        icon = get_icon_path()
        if icon:
            self._root.iconbitmap(icon)

        w, h = 400, 300 if needs_password else 260
        sw, sh = self._root.winfo_screenwidth(), self._root.winfo_screenheight()
        self._root.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

        self._build_ui()

    # ── UI construction ────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        tk.Label(
            self._root, text="⏸  Cancel Sleep Timer",
            font=("Segoe UI", 16, "bold"), bg=_BG, fg=_ACCENT,
        ).pack(pady=(24, 8))

        if self._needs_password:
            tk.Label(
                self._root, text="Enter cancellation password:",
                bg=_BG, fg=_FG, font=("Segoe UI", 11),
            ).pack(pady=(12, 4))
            self._pw_var = tk.StringVar()
            self._pw_entry = tk.Entry(
                self._root, textvariable=self._pw_var,
                show="•", width=22, justify="center",
                bg=_ENTRY, fg=_FG, insertbackground=_FG,
                font=("Segoe UI", 14), relief="flat", bd=8,
            )
            self._pw_entry.pack(pady=(0, 8))
            self._pw_entry.focus_set()
            self._root.bind("<Return>", lambda _e: self._submit())
        else:
            tk.Label(
                self._root,
                text="No password set.\nClick below to cancel the timer.",
                bg=_BG, fg=_FG, font=("Segoe UI", 11), justify="center",
            ).pack(pady=(16, 8))
            self._pw_var = tk.StringVar()

        # Status line (errors / success shown here)
        self._status_var = tk.StringVar()
        self._status_lbl = tk.Label(
            self._root, textvariable=self._status_var,
            bg=_BG, fg=_RED, font=("Segoe UI", 10, "italic"),
            wraplength=340, justify="center",
        )
        self._status_lbl.pack(pady=(4, 0))

        # Cancel button
        self._btn = tk.Button(
            self._root,
            text="✖  Cancel timer",
            bg=_RED, fg="#ffffff",
            activebackground="#c02026", activeforeground="#ffffff",
            font=("Segoe UI", 11, "bold"),
            relief="flat", bd=0, padx=24, pady=12,
            cursor="hand2",
            command=self._submit,
        )
        self._btn.pack(pady=(16, 24))

        # Hover effect
        def on_enter(e):
            if self._btn["state"] == "normal":
                self._btn.config(bg="#c02026")
        def on_leave(e):
            if self._btn["state"] == "normal":
                self._btn.config(bg=_RED)

        self._btn.bind("<Enter>", on_enter)
        self._btn.bind("<Leave>", on_leave)

    # ── Button logic ───────────────────────────────────────────────────────
    def _submit(self) -> None:
        pw = self._pw_var.get()
        self._set_loading()
        threading.Thread(target=self._do_check, args=(pw,), daemon=True).start()

    def _do_check(self, pw: str) -> None:
        result = self._on_submit(pw)
        self._root.after(0, self._on_result, result)

    def _on_result(self, result: str) -> None:
        if result == "ack":
            self._set_status("✅  Timer cancelled. Computer will stay on.", _GREEN)
            self._btn.config(state="disabled")
            self._root.after(2500, self._root.destroy)
        elif result == "nack":
            self._set_status("❌  Wrong password. Try again.", _RED)
            self._enable_submit()
            if self._needs_password:
                self._pw_var.set("")
                self._pw_entry.focus_set()
        else:  # timeout
            self._set_status("⚠  No response — timer may have already fired.", _YELLOW)
            self._root.after(3000, self._root.destroy)

    # ── State helpers ──────────────────────────────────────────────────────
    def _set_loading(self) -> None:
        self._set_status("⏳  Checking…", _FG)
        self._btn.config(state="disabled", text="Checking…")
        if self._needs_password:
            self._pw_entry.config(state="disabled")

    def _enable_submit(self) -> None:
        self._btn.config(state="normal", text="✖  Cancel timer")
        if self._needs_password:
            self._pw_entry.config(state="normal")

    def _set_status(self, msg: str, color: str) -> None:
        self._status_var.set(msg)
        self._status_lbl.config(fg=color)

    def _on_close(self) -> None:
        """X button — just close, do NOT send a cancel signal."""
        self._root.destroy()

    # ── Run ────────────────────────────────────────────────────────────────
    def run(self) -> None:
        self._root.mainloop()
