"""
tray.py — System-tray icon shown while the timer is active.

The icon is a minimal clock image generated with Pillow (no external asset
files needed).  The menu has no useful entry for the brother — only a
grayed-out status label.
"""
from __future__ import annotations

import threading
from datetime import timedelta
from typing import Callable, Optional

import pystray
from PIL import Image, ImageDraw


# ── Icon drawing ───────────────────────────────────────────────────────────
def _make_icon_image(size: int = 64) -> Image.Image:
    """Draw a simple clock face as a PIL Image."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    cx, cy, r = size // 2, size // 2, size // 2 - 2
    # Clock face
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(40, 40, 60), outline=(180, 180, 220), width=2)
    # Hour hand (pointing ~10)
    import math
    for angle, length, width in [(210, r * 0.5, 3), (300, r * 0.7, 2)]:
        rad = math.radians(angle - 90)
        x2 = cx + length * math.cos(rad)
        y2 = cy + length * math.sin(rad)
        draw.line([(cx, cy), (x2, y2)], fill=(220, 220, 255), width=width)
    # Center dot
    draw.ellipse([cx - 2, cy - 2, cx + 2, cy + 2], fill=(255, 255, 255))
    return img


# ── Tray class ─────────────────────────────────────────────────────────────
class SleepTray:
    """Manages the system-tray icon while the shutdown timer is active.

    Args:
        on_stop: Called when the tray is stopped (timer fired or cancelled).
    """

    def __init__(self, on_stop: Optional[Callable[[], None]] = None) -> None:
        self._on_stop = on_stop
        self._icon: Optional[pystray.Icon] = None
        self._thread: Optional[threading.Thread] = None

    # ── Public API ─────────────────────────────────────────────────────────
    def start(self) -> None:
        """Start the tray icon in a daemon thread."""
        menu = pystray.Menu(
            pystray.MenuItem("Sleep timer active", None, enabled=False),
        )
        self._icon = pystray.Icon(
            name="windows-auto-sleep",
            icon=_make_icon_image(),
            title="Sleep Timer",
            menu=menu,
        )
        self._thread = threading.Thread(
            target=self._icon.run,
            daemon=True,
            name="tray-icon",
        )
        self._thread.start()

    def stop(self) -> None:
        """Remove the tray icon and clean up."""
        if self._icon is not None:
            self._icon.stop()
            self._icon = None
        if self._on_stop is not None:
            self._on_stop()
