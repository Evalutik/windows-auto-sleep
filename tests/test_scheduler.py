"""
test_scheduler.py — Unit tests for core/scheduler.py.

All tests use very short timeouts (milliseconds) so the suite runs fast.
The actual shutdown callback is never called for real — we only test that
it IS or IS NOT called.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta

import pytest

from core.scheduler import ShutdownScheduler


# ── Helpers ────────────────────────────────────────────────────────────────
class _Flag:
    def __init__(self) -> None:
        self.called = False
        self.event  = threading.Event()

    def trigger(self) -> None:
        self.called = True
        self.event.set()

    def wait(self, timeout: float = 2.0) -> bool:
        return self.event.wait(timeout)


# ── schedule_duration ──────────────────────────────────────────────────────
class TestScheduleDuration:
    def test_fires_after_delay(self) -> None:
        flag = _Flag()
        s = ShutdownScheduler(callback=flag.trigger)
        s.schedule_duration(minutes=0.01)   # ~0.6 s
        assert flag.wait(timeout=2.0), "Callback was not called within timeout"
        assert flag.called

    def test_does_not_fire_when_cancelled(self) -> None:
        flag = _Flag()
        s = ShutdownScheduler(callback=flag.trigger)
        s.schedule_duration(minutes=0.5)    # 30 s — long enough to cancel
        time.sleep(0.05)
        s.cancel()
        assert not flag.wait(timeout=0.3), "Callback should NOT have been called after cancel"

    def test_rejects_zero_minutes(self) -> None:
        s = ShutdownScheduler(callback=lambda: None)
        with pytest.raises(ValueError):
            s.schedule_duration(minutes=0)

    def test_rejects_negative_minutes(self) -> None:
        s = ShutdownScheduler(callback=lambda: None)
        with pytest.raises(ValueError):
            s.schedule_duration(minutes=-5)

    def test_is_active_while_running(self) -> None:
        flag = _Flag()
        s = ShutdownScheduler(callback=flag.trigger)
        s.schedule_duration(minutes=1)
        assert s.is_active
        s.cancel()

    def test_is_not_active_after_cancel(self) -> None:
        s = ShutdownScheduler(callback=lambda: None)
        s.schedule_duration(minutes=1)
        s.cancel()
        s._thread.join(timeout=1.0)
        assert not s.is_active

    def test_rejects_double_start(self) -> None:
        s = ShutdownScheduler(callback=lambda: None)
        s.schedule_duration(minutes=1)
        with pytest.raises(RuntimeError):
            s.schedule_duration(minutes=1)
        s.cancel()


# ── schedule_at ────────────────────────────────────────────────────────────
class TestScheduleAt:
    def test_fires_at_target_time(self) -> None:
        flag = _Flag()
        s = ShutdownScheduler(callback=flag.trigger)
        target = datetime.now() + timedelta(seconds=0.6)
        s.schedule_at(target)
        assert flag.wait(timeout=2.0), "Callback was not called within timeout"

    def test_rejects_past_time(self) -> None:
        s = ShutdownScheduler(callback=lambda: None)
        past = datetime.now() - timedelta(seconds=1)
        with pytest.raises(ValueError):
            s.schedule_at(past)


# ── time_remaining ─────────────────────────────────────────────────────────
class TestTimeRemaining:
    def test_none_before_schedule(self) -> None:
        s = ShutdownScheduler(callback=lambda: None)
        assert s.time_remaining() is None

    def test_positive_while_running(self) -> None:
        s = ShutdownScheduler(callback=lambda: None)
        s.schedule_duration(minutes=10)
        rem = s.time_remaining()
        assert rem is not None
        assert rem.total_seconds() > 0
        s.cancel()

    def test_cancel_is_idempotent(self) -> None:
        s = ShutdownScheduler(callback=lambda: None)
        s.schedule_duration(minutes=1)
        s.cancel()
        s.cancel()   # should not raise
