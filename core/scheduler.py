"""
scheduler.py — Countdown / target-time shutdown scheduler.

Uses a threading.Event so cancellation is instant with no busy-loop.
"""
from __future__ import annotations

import threading
from datetime import datetime, timedelta
from typing import Callable, Optional


class ShutdownScheduler:
    """Schedules a single callback after a duration or at a specific time.

    Usage::

        s = ShutdownScheduler(callback=my_shutdown_fn)
        s.schedule_duration(minutes=30)
        # … later …
        s.cancel()
    """

    def __init__(self, callback: Callable[[], None]) -> None:
        self._callback = callback
        self._cancel_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._fire_at: Optional[datetime] = None

    # ── Public scheduling API ──────────────────────────────────────────────
    def schedule_duration(self, minutes: float) -> None:
        """Start a timer that fires after *minutes* minutes."""
        if minutes <= 0:
            raise ValueError("minutes must be positive")
        self._fire_at = datetime.now() + timedelta(minutes=minutes)
        self._start()

    def schedule_at(self, target: datetime) -> None:
        """Start a timer that fires at an absolute *target* time."""
        if target <= datetime.now():
            raise ValueError("target time must be in the future")
        self._fire_at = target
        self._start()

    def cancel(self) -> None:
        """Cancel a pending timer. Safe to call even if nothing is scheduled."""
        self._cancel_event.set()

    # ── State inspection ───────────────────────────────────────────────────
    @property
    def is_active(self) -> bool:
        """True while the background thread is alive (i.e. timer is pending)."""
        return self._thread is not None and self._thread.is_alive()

    def time_remaining(self) -> Optional[timedelta]:
        """Remaining time, or None if not scheduled, or timedelta(0) if overdue."""
        if self._fire_at is None:
            return None
        delta = self._fire_at - datetime.now()
        return delta if delta.total_seconds() > 0 else timedelta(0)

    # ── Internal ───────────────────────────────────────────────────────────
    def _start(self) -> None:
        if self.is_active:
            raise RuntimeError("Scheduler is already running; call cancel() first")
        self._cancel_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="sleep-timer")
        self._thread.start()

    def _run(self) -> None:
        delay_s = (self._fire_at - datetime.now()).total_seconds()
        if delay_s > 0:
            cancelled = self._cancel_event.wait(timeout=delay_s)
        else:
            cancelled = False

        if not cancelled:
            self._callback()
