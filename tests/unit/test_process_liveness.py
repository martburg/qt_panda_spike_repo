from __future__ import annotations

import os
import subprocess
import sys

from steuerung3d.core.process_liveness import pid_is_alive


def test_pid_is_alive_detects_current_process() -> None:
    assert pid_is_alive(os.getpid()) is True


def test_pid_is_alive_detects_finished_child() -> None:
    child = subprocess.Popen([sys.executable, "-c", "print('ok')"])
    child.wait(timeout=5.0)
    assert pid_is_alive(int(child.pid)) is False
