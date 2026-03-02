from __future__ import annotations

import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

# ---- edit these as needed ----
AXIS_ID = "X"
DEN_SI_DT = "0.1"
LOG_LEVEL = "debug"

CORE_CMD = f"python -m steuerung3d.apps.core_udp_service --log-level {LOG_LEVEL}"
DEN_SI_CMD = f"python -m steuerung3d.apps.den_si --axis {AXIS_ID} --dt {DEN_SI_DT} --log-level {LOG_LEVEL}"
HIP_CMD  = f"python -m steuerung3d.apps.hi_p --log-level {LOG_LEVEL}"


def _run(cmd: list[str]) -> None:
    subprocess.Popen(cmd, cwd=os.getcwd())


def launch_with_windows_terminal() -> None:
    # Window #1: core
    _run([
        "wt",
        "new-tab", "--title", "core",
        "cmd.exe", "/k", CORE_CMD
    ])

    # Window #2: den-si + hi-p split panes
    # Start den-si in first pane, split vertical for hi-p.
    _run([
        "wt",
        "new-tab", "--title", "den-si",
        "cmd.exe", "/k", DEN_SI_CMD,
        ";",
        "split-pane", "-V", "--title", "hi-p",
        "cmd.exe", "/k", HIP_CMD
    ])


def launch_with_powershell_fallback() -> None:
    """
    Fallback without Windows Terminal:
      - Window #1 runs core (live)
      - Window #2 runs den-si + hi-p (live, interleaved) BUT also writes each to its own log file.
    """
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")

    core_log = logs_dir / f"core-{ts}.log"
    den_log  = logs_dir / f"den-si-{ts}.log"
    hip_log  = logs_dir / f"hi-p-{ts}.log"

    # Window #1
    subprocess.Popen(
        ["powershell", "-NoExit", "-Command", f'{CORE_CMD} *>> "{core_log}"'],
        creationflags=subprocess.CREATE_NEW_CONSOLE,
        cwd=os.getcwd(),
    )

    # Window #2
    # Run both as background jobs so the console stays usable; logs go to separate files.
    ps = (
        f'Start-Job -ScriptBlock {{ {DEN_SI_CMD} *>> "{den_log}" }} | Out-Null; '
        f'Start-Job -ScriptBlock {{ {HIP_CMD} *>> "{hip_log}" }} | Out-Null; '
        f'Write-Host "den-si -> {den_log}"; '
        f'Write-Host "hi-p   -> {hip_log}"; '
        f'Write-Host "Close this window to stop jobs (or run: Get-Job | Stop-Job | Remove-Job)";'
    )
    subprocess.Popen(
        ["powershell", "-NoExit", "-Command", ps],
        creationflags=subprocess.CREATE_NEW_CONSOLE,
        cwd=os.getcwd(),
    )


def main() -> None:
    if shutil.which("wt"):
        launch_with_windows_terminal()
    else:
        launch_with_powershell_fallback()


if __name__ == "__main__":
    main()
