"""
activation_window.py — Tkinter UI shown on first launch (no timer running).

Two modes are presented in the same window via a ttk.Notebook:
  Tab 1 – "Duration"   : shut down in N minutes
  Tab 2 – "At time"    : shut down at HH:MM (today or tomorrow)

An optional password field lets the parent lock cancellation.
An "Uninstall" button (bottom-left) removes all app data when no timer is
running.

After "Activate" is clicked the window destroys itself; the caller is
responsible for hiding to the tray.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from datetime import datetime, timedelta
from typing import Callable, Optional


# ── Colour palette ─────────────────────────────────────────────────────────
_BG      = "#1e1e2e"   # dark background
_FG      = "#cdd6f4"   # text
_ACCENT  = "#89b4fa"   # blue accent
_ENTRY   = "#313244"   # entry background
_BTN     = "#45475a"   # normal button
_BTN_ACT = "#89b4fa"   # activate button
_RED     = "#f38ba8"   # uninstall / warning


class ActivationWindow:
    """Modal window for scheduling a shutdown.

    Args:
        on_activate:  Called with (minutes: float, password: str).
                      ``password`` is an empty string if the user left it blank.
        on_uninstall: Called when the user confirms the uninstall action.
    """

    def __init__(
        self,
        on_activate:  Callable[[float, str], None],
        on_uninstall: Callable[[], None],
    ) -> None:
        self._on_activate  = on_activate
        self._on_uninstall = on_uninstall

        self._root = tk.Tk()
        self._root.title("Sleep Timer — Setup")
        self._root.resizable(False, False)
        self._root.configure(bg=_BG)
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Centre on screen
        self._root.update_idletasks()
        w, h = 380, 340
        sw = self._root.winfo_screenwidth()
        sh = self._root.winfo_screenheight()
        self._root.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

        # Keep on top so it's clearly visible at the start
        self._root.attributes("-topmost", True)

        self._build_styles()
        self._build_ui()

    # ── Styles ─────────────────────────────────────────────────────────────
    def _build_styles(self) -> None:
        style = ttk.Style(self._root)
        style.theme_use("clam")
        style.configure(".", background=_BG, foreground=_FG, font=("Segoe UI", 10))
        style.configure("TNotebook",        background=_BG, borderwidth=0)
        style.configure("TNotebook.Tab",    background=_BTN, foreground=_FG,
                         padding=[12, 4], font=("Segoe UI", 10))
        style.map("TNotebook.Tab",
                  background=[("selected", _ACCENT)],
                  foreground=[("selected", _BG)])
        style.configure("TFrame",  background=_BG)
        style.configure("TLabel",  background=_BG, foreground=_FG)
        style.configure("TEntry",  fieldbackground=_ENTRY, foreground=_FG,
                         insertcolor=_FG, borderwidth=0)
        style.configure("TSpinbox", fieldbackground=_ENTRY, foreground=_FG,
                         arrowsize=12, borderwidth=0)
        style.configure("Accent.TButton",
                         background=_BTN_ACT, foreground=_BG,
                         font=("Segoe UI", 10, "bold"), padding=[10, 5])
        style.map("Accent.TButton",
                  background=[("active", "#74c7ec"), ("pressed", "#74c7ec")])
        style.configure("Uninstall.TButton",
                         background=_RED, foreground=_BG,
                         font=("Segoe UI", 9), padding=[6, 3])
        style.map("Uninstall.TButton",
                  background=[("active", "#eba0ac"), ("pressed", "#eba0ac")])

    # ── UI construction ────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        pad = {"padx": 16, "pady": 6}

        # Title
        tk.Label(
            self._root, text="🕐  Sleep Timer",
            font=("Segoe UI", 14, "bold"),
            bg=_BG, fg=_ACCENT,
        ).pack(pady=(18, 4))

        # Notebook (Duration / At time)
        nb = ttk.Notebook(self._root)
        nb.pack(fill="x", padx=16, pady=6)

        self._tab_duration(nb)
        self._tab_attime(nb)
        self._nb = nb

        # Separator
        ttk.Separator(self._root, orient="horizontal").pack(fill="x", padx=16, pady=8)

        # Password row
        pw_frame = ttk.Frame(self._root)
        pw_frame.pack(fill="x", **pad)
        ttk.Label(pw_frame, text="Password (optional):").pack(side="left")
        self._pw_var = tk.StringVar()
        self._pw_entry = ttk.Entry(pw_frame, textvariable=self._pw_var,
                                    show="•", width=18)
        self._pw_entry.pack(side="right")

        # Confirm password row
        pw2_frame = ttk.Frame(self._root)
        pw2_frame.pack(fill="x", **pad)
        ttk.Label(pw2_frame, text="Confirm password:").pack(side="left")
        self._pw2_var = tk.StringVar()
        self._pw2_entry = ttk.Entry(pw2_frame, textvariable=self._pw2_var,
                                     show="•", width=18)
        self._pw2_entry.pack(side="right")

        # Buttons row
        btn_frame = ttk.Frame(self._root)
        btn_frame.pack(fill="x", padx=16, pady=(10, 16))

        ttk.Button(
            btn_frame, text="🗑 Uninstall",
            style="Uninstall.TButton",
            command=self._on_uninstall_click,
        ).pack(side="left")

        ttk.Button(
            btn_frame, text="Activate  ▶",
            style="Accent.TButton",
            command=self._on_activate_click,
        ).pack(side="right")

    def _tab_duration(self, nb: ttk.Notebook) -> None:
        f = ttk.Frame(nb)
        nb.add(f, text="  Duration  ")
        inner = ttk.Frame(f)
        inner.pack(expand=True, pady=14)
        ttk.Label(inner, text="Shut down in").pack(side="left", padx=(0, 6))
        self._dur_var = tk.IntVar(value=30)
        ttk.Spinbox(
            inner, from_=1, to=1440, width=5,
            textvariable=self._dur_var,
            font=("Segoe UI", 11),
        ).pack(side="left")
        ttk.Label(inner, text="minutes").pack(side="left", padx=(6, 0))

    def _tab_attime(self, nb: ttk.Notebook) -> None:
        f = ttk.Frame(nb)
        nb.add(f, text="  At time  ")
        inner = ttk.Frame(f)
        inner.pack(expand=True, pady=14)
        ttk.Label(inner, text="Shut down at").pack(side="left", padx=(0, 6))
        self._time_var = tk.StringVar(value=datetime.now().strftime("%H:%M"))
        ttk.Entry(inner, textvariable=self._time_var, width=7,
                  font=("Segoe UI", 11), justify="center").pack(side="left")
        ttk.Label(inner, text="(HH:MM, 24h)").pack(side="left", padx=(6, 0))

    # ── Button handlers ────────────────────────────────────────────────────
    def _on_activate_click(self) -> None:
        pw  = self._pw_var.get()
        pw2 = self._pw2_var.get()

        if pw != pw2:
            messagebox.showerror("Password mismatch",
                                 "The two password fields don't match.",
                                 parent=self._root)
            return

        minutes = self._resolve_minutes()
        if minutes is None:
            return   # error already shown inside _resolve_minutes

        self._root.destroy()
        self._on_activate(minutes, pw)

    def _resolve_minutes(self) -> Optional[float]:
        tab = self._nb.index("current")
        if tab == 0:
            # Duration tab
            try:
                m = int(self._dur_var.get())
                if m <= 0:
                    raise ValueError
                return float(m)
            except (ValueError, tk.TclError):
                messagebox.showerror("Invalid value",
                                     "Please enter a positive number of minutes.",
                                     parent=self._root)
                return None
        else:
            # At-time tab
            raw = self._time_var.get().strip()
            try:
                target = datetime.strptime(raw, "%H:%M").replace(
                    year=datetime.now().year,
                    month=datetime.now().month,
                    day=datetime.now().day,
                )
                if target <= datetime.now():
                    target += timedelta(days=1)   # tomorrow
                delta = target - datetime.now()
                return delta.total_seconds() / 60
            except ValueError:
                messagebox.showerror("Invalid time",
                                     f'Could not parse "{raw}".\nUse HH:MM (24h format).',
                                     parent=self._root)
                return None

    def _on_uninstall_click(self) -> None:
        confirmed = messagebox.askyesno(
            "Uninstall",
            "This will delete all app data (password file, config).\n"
            "The exe itself will NOT be deleted.\n\n"
            "Continue?",
            icon="warning",
            parent=self._root,
        )
        if confirmed:
            self._root.destroy()
            self._on_uninstall()

    def _on_close(self) -> None:
        """Window X button — just quit without scheduling anything."""
        self._root.destroy()

    # ── Run ────────────────────────────────────────────────────────────────
    def run(self) -> None:
        """Enter the Tkinter event loop (blocks until window is destroyed)."""
        self._root.mainloop()
