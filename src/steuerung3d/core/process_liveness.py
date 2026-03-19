from __future__ import annotations

import os


def pid_is_alive(pid: int) -> bool:
    """Best-effort cross-platform liveness probe.

    On POSIX, ``os.kill(pid, 0)`` is the normal existence check.
    On Windows, use ``OpenProcess`` + ``GetExitCodeProcess`` instead of
    ``os.kill(pid, 0)`` because the latter is not a harmless probe.
    """

    if pid <= 0:
        return False

    if os.name != "nt":
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True

    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        process = kernel32.OpenProcess(0x1000, False, wintypes.DWORD(pid))
        if not process:
            return False
        try:
            exit_code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(process, ctypes.byref(exit_code)):
                return False
            return int(exit_code.value) == 259  # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(process)
    except Exception:
        return False
