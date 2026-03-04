from __future__ import annotations

import logging

log = logging.getLogger("core_udp_service")


def show_fatal_modal(msg: str, *, title: str = "Steuerung3D – Core") -> None:
    """Best-effort modal error dialog (Windows-friendly).

    Falls back to stderr if tkinter is unavailable.
    """

    try:
        import tkinter as _tk
        from tkinter import messagebox as _mb
    except ImportError:
        _tk = None  # type: ignore[assignment]
        _mb = None  # type: ignore[assignment]

    if _tk is not None and _mb is not None:
        try:
            r = _tk.Tk()
            r.withdraw()
            _mb.showerror(title, msg)
            try:
                r.destroy()
            except Exception:
                pass
        except Exception:
            # Headless (TclError) or other UI failure: ignore.
            pass

    try:
        import sys as _sys

        print(msg, file=_sys.stderr)
    except Exception:
        pass


def fatal(msg: str) -> int:
    show_fatal_modal(msg)
    log.error(msg)
    return 2
