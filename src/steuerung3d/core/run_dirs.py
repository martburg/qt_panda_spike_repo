"""Run/session directory helpers.

This module centralizes the "session run dir" policy used by launchers such as
Profile-driven stack supervisors (historically also `setup_stack`, now removed).

Policy
  - Each run gets a fresh session directory under `<base>/sessions/<timestamp>/`.
  - A text file `<base>/LATEST` points to the newest session directory.
  - Old sessions are deleted, keeping only the most recent N sessions.

We intentionally avoid symlinks for the LATEST pointer (Windows friendliness).
"""

from __future__ import annotations

import shutil
import time
from pathlib import Path


def _safe_rmtree(p: Path) -> None:
    """Best-effort recursive delete (Windows-friendly)."""

    # Try a couple of times to reduce "permission denied" flakiness on Windows.
    for _ in range(3):
        try:
            shutil.rmtree(p, ignore_errors=False)
            return
        except FileNotFoundError:
            return
        except Exception:
            time.sleep(0.05)
    # Last try: ignore errors
    shutil.rmtree(p, ignore_errors=True)


def make_session_dir(
    base_dir: Path,
    *,
    keep_last: int = 5,
    sessions_subdir: str = "sessions",
    latest_filename: str = "LATEST",
    timestamp_fmt: str = "%Y%m%d_%H%M%S",
) -> Path:
    """Create and return a fresh session directory and apply rollover.

    Parameters
    ----------
    base_dir:
        Base directory for the launcher/run (e.g. `.run/<profile>`).
    keep_last:
        Number of most recent sessions to keep.
    sessions_subdir:
        Subdirectory name under `base_dir` that holds session folders.
    latest_filename:
        Pointer file name written under `base_dir` containing the newest
        session directory path.
    timestamp_fmt:
        Timestamp format for the session directory name.
    """

    base_dir = Path(base_dir)
    sessions_dir = base_dir / sessions_subdir
    sessions_dir.mkdir(parents=True, exist_ok=True)

    # Ensure uniqueness if started multiple times within the same second.
    stamp = time.strftime(timestamp_fmt)
    session_dir = sessions_dir / stamp
    suffix = 0
    while session_dir.exists():
        suffix += 1
        session_dir = sessions_dir / f"{stamp}_{suffix}"
    session_dir.mkdir(parents=True, exist_ok=False)

    # Write/update a plain-text pointer file to the latest session dir.
    try:
        (base_dir / latest_filename).write_text(str(session_dir), encoding="utf-8")
    except Exception:
        # Non-critical.
        pass

    # Rollover: keep only the newest N sessions.
    if keep_last is not None and keep_last > 0:
        try:
            session_paths = [p for p in sessions_dir.iterdir() if p.is_dir()]
            # Name sort works because we use a sortable timestamp prefix.
            session_paths.sort(key=lambda p: p.name)
            to_delete = session_paths[:-keep_last]
            for p in to_delete:
                _safe_rmtree(p)
        except Exception:
            # Non-critical.
            pass

    return session_dir
