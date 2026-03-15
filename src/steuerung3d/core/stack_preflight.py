from __future__ import annotations

import os
import re
import subprocess
import sys
from typing import Iterable

from .stack_spec import ProcessSpec

_BIND_FLAGS_EXACT = {
    "--intent-in",
    "--cmd-in",
    "--telem-in",
    "--action-in",
    "--dev-telem-in",
    "--status-in",
    "--raw-in",
}


def extract_bind_ports(processes: Iterable[ProcessSpec]) -> list[int]:
    ports: list[int] = []
    seen: set[int] = set()
    for proc in processes:
        argv = list(proc.argv)
        for i, token in enumerate(argv[:-1]):
            if not _is_bind_flag(str(token)):
                continue
            port = _parse_port(argv[i + 1])
            if port is None:
                continue
            if port not in seen:
                seen.add(port)
                ports.append(port)
    return ports


def _is_bind_flag(token: str) -> bool:
    t = str(token).strip()
    if t in _BIND_FLAGS_EXACT:
        return True
    if t.endswith("-in") and not t.endswith("-out"):
        return True
    return False


def _parse_port(value: object) -> int | None:
    s = str(value).strip()
    m = re.match(r"^.+:(\d+)$", s)
    if m is None:
        return None
    try:
        port = int(m.group(1))
    except Exception:
        return None
    return port if 0 < port < 65536 else None


def cleanup_residual_bind_ports(ports: Iterable[int]) -> list[int]:
    cleaned: list[int] = []
    for port in ports:
        pids = _pids_bound_to_udp_port(int(port))
        for pid in pids:
            if pid <= 0 or pid == os.getpid():
                continue
            if _kill_pid(pid):
                if int(port) not in cleaned:
                    cleaned.append(int(port))
    return cleaned


def _pids_bound_to_udp_port(port: int) -> list[int]:
    if sys.platform.startswith("win"):
        return _pids_bound_to_udp_port_windows(port)
    return _pids_bound_to_udp_port_posix(port)


def _pids_bound_to_udp_port_windows(port: int) -> list[int]:
    try:
        cp = subprocess.run(
            ["netstat", "-ano", "-p", "udp"],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return []
    pids: list[int] = []
    for line in str(cp.stdout).splitlines():
        if f":{port}" not in line:
            continue
        parts = line.split()
        if len(parts) < 4:
            continue
        local = parts[1]
        if not local.endswith(f":{port}"):
            continue
        try:
            pid = int(parts[-1])
        except Exception:
            continue
        if pid not in pids:
            pids.append(pid)
    return pids


def _pids_bound_to_udp_port_posix(port: int) -> list[int]:
    cmds = [
        ["lsof", "-ti", f"udp:{port}"],
        ["ss", "-lunp"],
    ]
    for cmd in cmds:
        try:
            cp = subprocess.run(cmd, capture_output=True, text=True, check=False)
        except Exception:
            continue
        out = str(cp.stdout)
        if cmd[0] == "lsof":
            pids: list[int] = []
            for line in out.splitlines():
                try:
                    pid = int(line.strip())
                except Exception:
                    continue
                if pid not in pids:
                    pids.append(pid)
            if pids:
                return pids
        else:
            pids: list[int] = []
            pat = re.compile(rf":{port}\s+.*pid=(\d+)")
            for line in out.splitlines():
                m = pat.search(line)
                if not m:
                    continue
                try:
                    pid = int(m.group(1))
                except Exception:
                    continue
                if pid not in pids:
                    pids.append(pid)
            if pids:
                return pids
    return []


def _kill_pid(pid: int) -> bool:
    if sys.platform.startswith("win"):
        try:
            cp = subprocess.run(
                ["taskkill", "/PID", str(pid), "/F"],
                capture_output=True,
                text=True,
                check=False,
            )
            return cp.returncode == 0
        except Exception:
            return False
    try:
        os.kill(pid, 15)
        return True
    except Exception:
        return False
