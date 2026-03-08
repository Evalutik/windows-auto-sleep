# gui package

import os
import sys

def get_icon_path() -> str:
    """Return the path to the app icon, supporting PyInstaller's _MEIPASS."""
    try:
        base = sys._MEIPASS
    except Exception:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    icon_path = os.path.join(base, "icon.ico")
    return icon_path if os.path.exists(icon_path) else ""
