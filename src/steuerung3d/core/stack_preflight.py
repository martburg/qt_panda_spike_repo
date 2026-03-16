from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Iterable

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib

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


def _append_unique_int(out: list[int], seen: set[int], value: int | None) -> None:
    if value is None or value in seen:
        return
    seen.add(value)
    out.append(value)


def extract_bind_ports(processes: Iterable[ProcessSpec]) -> list[int]:
    ports: list[int] = []
    seen: set[int] = set()

    for proc in processes:
        argv = list(proc.argv)
        for i, token in enumerate(argv[:-1]):
            if not _is_bind_flag(str(token)):
                continue
            _append_unique_int(ports, seen, _parse_port(argv[i + 1]))
        for cfg_path in _config_paths_from_argv(argv):
            for port in _extract_bind_ports_from_config(cfg_path):
                _append_unique_int(ports, seen, port)
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


def _parse_netstat_udp_pids(output: str, *, port: int) -> list[int]:
    pids: list[int] = []
    seen: set[int] = set()
    for line in output.splitlines():
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
        _append_unique_int(pids, seen, pid)
    return pids


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
    return _parse_netstat_udp_pids(str(cp.stdout), port=port)


def _parse_lsof_udp_pids(output: str) -> list[int]:
    pids: list[int] = []
    seen: set[int] = set()
    for line in output.splitlines():
        try:
            pid = int(line.strip())
        except Exception:
            continue
        _append_unique_int(pids, seen, pid)
    return pids


def _parse_ss_udp_pids(output: str, *, port: int) -> list[int]:
    pids: list[int] = []
    seen: set[int] = set()
    pat = re.compile(rf":{port}\s+.*pid=(\d+)")
    for line in output.splitlines():
        m = pat.search(line)
        if not m:
            continue
        try:
            pid = int(m.group(1))
        except Exception:
            continue
        _append_unique_int(pids, seen, pid)
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
        pids = _parse_lsof_udp_pids(out) if cmd[0] == "lsof" else _parse_ss_udp_pids(out, port=port)
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


def _config_paths_from_argv(argv: list[object]) -> list[Path]:
    out: list[Path] = []
    for i, token in enumerate(argv[:-1]):
        if str(token).strip() != "--config":
            continue
        cfg = Path(str(argv[i + 1]).strip())
        if cfg not in out:
            out.append(cfg)
    return out


def _add_inbound_ports_from_mapping(mapping: object, ports: list[int], seen: set[int]) -> None:
    if not isinstance(mapping, dict):
        return
    for key, value in mapping.items():
        key_s = str(key).strip().lower()
        if key_s.endswith("_in"):
            _append_unique_int(ports, seen, _parse_port(value))


def _extract_bind_ports_from_config(path: Path) -> list[int]:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    ports: list[int] = []
    seen: set[int] = set()
    _add_inbound_ports_from_mapping(data.get("io"), ports, seen)
    _add_inbound_ports_from_mapping(data.get("net"), ports, seen)
    return ports
