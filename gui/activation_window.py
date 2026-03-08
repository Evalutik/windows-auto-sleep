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

from gui import get_icon_path


# ── Colour palette ─────────────────────────────────────────────────────────
_BG      = "#313338"   # dark background
_FG      = "#dbdee1"   # text
_ACCENT  = "#5865F2"   # blurple accent
_ENTRY   = "#1e1f22"   # entry background
_BTN     = "#4e5058"   # normal button
_BTN_ACT = "#5865F2"   # activate button
_RED     = "#da373c"   # uninstall / warning


class ActivationWindow:
    """Modal window for scheduling a shutdown.

    Args:
        on_activate:  Called with (minutes: float, password: str, action: str).
                      ``password`` is an empty string if the user left it blank.
                      ``action`` is either "block" or "shutdown".
        on_uninstall: Called when the user confirms the uninstall action.
    """

    def __init__(
        self,
        on_activate:  Callable[[float, str, str], None],
        on_uninstall: Callable[[], None],
    ) -> None:
        self._on_activate  = on_activate
        self._on_uninstall = on_uninstall

        self._root = tk.Tk()
        self._root.title("Sleep Timer — Setup")
        self._root.resizable(False, False)
        self._root.configure(bg=_BG)
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)
        
        icon = get_icon_path()
        if icon:
            self._root.iconbitmap(icon)

        # Centre on screen
        self._root.update_idletasks()
        w, h = 420, 540
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
        style.configure("TNotebook",        background=_BG, borderwidth=0, padding=0)
        style.configure("TNotebook.Tab",    background=_ENTRY, foreground=_FG,
                         padding=[20, 8], font=("Segoe UI", 10, "bold"), borderwidth=0)
        style.map("TNotebook.Tab",
                  background=[("selected", _BTN)],
                  foreground=[("selected", "#ffffff")])
        style.configure("TFrame",  background=_BG)
        style.configure("TLabel",  background=_BG, foreground=_FG, font=("Segoe UI", 10))
        # (We use tk.Button, tk.Entry, tk.Spinbox, tk.Radiobutton directly for flat modern styles)

    # ── UI construction ────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        pad = {"padx": 24, "pady": 8}

        # Title
        tk.Label(
            self._root, text="🕐  Sleep Timer",
            font=("Segoe UI", 16, "bold"),
            bg=_BG, fg=_ACCENT,
        ).pack(pady=(24, 8))

        # Notebook (Duration / At time)
        nb = ttk.Notebook(self._root)
        nb.pack(fill="x", padx=24, pady=8)

        self._tab_duration(nb)
        self._tab_attime(nb)
        self._nb = nb

        # Separator
        ttk.Separator(self._root, orient="horizontal").pack(fill="x", padx=24, pady=8)

        # Action selection row
        action_frame = ttk.Frame(self._root)
        action_frame.pack(fill="x", **pad)
        ttk.Label(action_frame, text="Action:", font=("Segoe UI", 10, "bold")).pack(side="left", padx=(0, 16))
        self._action_var = tk.StringVar(value="block")
        
        rb_frame = ttk.Frame(action_frame)
        rb_frame.pack(side="left")
        tk.Radiobutton(
            rb_frame, text="Block screen", value="block", variable=self._action_var,
            bg=_BG, fg=_FG, font=("Segoe UI", 10),
            selectcolor=_ENTRY, activebackground=_BG, activeforeground=_FG,
            cursor="hand2"
        ).pack(side="top", anchor="w", pady=4)
        tk.Radiobutton(
            rb_frame, text="Turn off PC", value="shutdown", variable=self._action_var,
            bg=_BG, fg=_FG, font=("Segoe UI", 10),
            selectcolor=_ENTRY, activebackground=_BG, activeforeground=_FG,
            cursor="hand2"
        ).pack(side="top", anchor="w", pady=4)

        # Separator
        ttk.Separator(self._root, orient="horizontal").pack(fill="x", padx=24, pady=8)

        # Password row
        pw_frame = ttk.Frame(self._root)
        pw_frame.pack(fill="x", **pad)
        ttk.Label(pw_frame, text="Password (optional):").pack(side="left")
        self._pw_var = tk.StringVar()
        self._pw_entry = tk.Entry(pw_frame, textvariable=self._pw_var,
                                    show="•", width=18, font=("Segoe UI", 12),
                                    bg=_ENTRY, fg=_FG, insertbackground=_FG,
                                    relief="flat", bd=6)
        self._pw_entry.pack(side="right")

        # Confirm password row
        pw2_frame = ttk.Frame(self._root)
        pw2_frame.pack(fill="x", **pad)
        ttk.Label(pw2_frame, text="Confirm password:").pack(side="left")
        self._pw2_var = tk.StringVar()
        self._pw2_entry = tk.Entry(pw2_frame, textvariable=self._pw2_var,
                                     show="•", width=18, font=("Segoe UI", 12),
                                     bg=_ENTRY, fg=_FG, insertbackground=_FG,
                                     relief="flat", bd=6)
        self._pw2_entry.pack(side="right")

        # Buttons row
        btn_frame = ttk.Frame(self._root)
        btn_frame.pack(fill="x", padx=24, pady=(24, 28))

        un_btn = tk.Button(
            btn_frame, text="🗑 Uninstall",
            bg=_BG, fg=_RED,
            activebackground=_ENTRY, activeforeground=_RED,
            font=("Segoe UI", 10, "bold"),
            relief="flat", bd=0, padx=16, pady=8,
            cursor="hand2",
            command=self._on_uninstall_click,
        )
        un_btn.pack(side="left")

        act_btn = tk.Button(
            btn_frame, text="Activate  ▶",
            bg=_BTN_ACT, fg="#ffffff",
            activebackground="#4752c4", activeforeground="#ffffff",
            font=("Segoe UI", 11, "bold"),
            relief="flat", bd=0, padx=28, pady=12,
            cursor="hand2",
            command=self._on_activate_click,
        )
        act_btn.pack(side="right")

        # Hover effects
        def on_enter_act(e): act_btn.config(bg="#4752c4")
        def on_leave_act(e): act_btn.config(bg=_BTN_ACT)
        def on_enter_un(e):  un_btn.config(bg=_ENTRY)
        def on_leave_un(e):  un_btn.config(bg=_BG)

        act_btn.bind("<Enter>", on_enter_act)
        act_btn.bind("<Leave>", on_leave_act)
        un_btn.bind("<Enter>", on_enter_un)
        un_btn.bind("<Leave>", on_leave_un)

    def _tab_duration(self, nb: ttk.Notebook) -> None:
        f = ttk.Frame(nb)
        nb.add(f, text="    Duration    ")
        inner = ttk.Frame(f)
        inner.pack(expand=True, pady=24)
        ttk.Label(inner, text="Shut down in", font=("Segoe UI", 11)).pack(side="left", padx=(0, 10))
        self._dur_var = tk.StringVar(value="30")
        tk.Spinbox(
            inner, from_=1, to=1440, width=5,
            textvariable=self._dur_var,
            font=("Segoe UI", 14),
            bg=_ENTRY, fg=_FG, insertbackground=_FG,
            buttonbackground=_ENTRY, relief="flat", bd=6
        ).pack(side="left")
        ttk.Label(inner, text="minutes", font=("Segoe UI", 11)).pack(side="left", padx=(10, 0))

    def _tab_attime(self, nb: ttk.Notebook) -> None:
        f = ttk.Frame(nb)
        nb.add(f, text="    At time    ")
        inner = ttk.Frame(f)
        inner.pack(expand=True, pady=24)
        ttk.Label(inner, text="Shut down at", font=("Segoe UI", 11)).pack(side="left", padx=(0, 10))
        self._time_var = tk.StringVar(value=datetime.now().strftime("%H:%M"))
        tk.Entry(inner, textvariable=self._time_var, width=7,
                  font=("Segoe UI", 14), justify="center",
                  bg=_ENTRY, fg=_FG, insertbackground=_FG,
                  relief="flat", bd=6).pack(side="left")
        ttk.Label(inner, text="(HH:MM, 24h)", font=("Segoe UI", 10)).pack(side="left", padx=(10, 0))

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
        self._on_activate(minutes, pw, self._action_var.get())

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
