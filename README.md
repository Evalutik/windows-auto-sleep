# Windows Auto-Sleep

A lightweight Windows tool to force-shutdown your PC after a timer or at a specific time. Designed to be simple but hard to bypass—requires a password to cancel once active.

## Why this?
Most "sleep timers" can be easily skipped by clicking a "Cancel" button on an windowsconfirmation message, just a few seconds before shut down. This one uses Windows kernel objects and NTFS file permissions to make it actually stick. Great for anyone who needs a hard stop for their PC time.

## Features
- **Force Shutdown**: Uses the proper Windows API to kill all processes and power off without asking.
- **Lock-in**: Optional password protection for cancellation.
- **Stealth**: Once active, it hides to the system tray. No distracting windows.
- **Secure**: Passwords are Bcrypt-hashed and protected with NTFS "deny delete" permissions.
- **One-time Passwords**: Passwords expire after use or shutdown. No stale config leftovers.

## Setup
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Run it:
   ```bash
   python main.py
   ```

## Building the .exe
To turn it into a single standalone file that always runs as Administrator:
```bash
pyinstaller build.spec
```
The result will be in the `dist/` folder.

## Technical Details
- **IPC**: Uses Named Mutex and Events for inter-process sync.
- **UI**: Pure Python/Tkinter (custom dark theme).
- **Core**: Leverages `pywin32` for low-level Windows integration.


