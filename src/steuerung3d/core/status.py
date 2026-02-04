"""Structured status heartbeat (side-channel) for birds-eye supervision.

This is intentionally small and dependency-free:
- Children emit JSON heartbeats over UDP (best-effort)
- Supervisor collects and prints a birds-eye line (preferred over log-grep)

Enabled by environment:
  ST3D_STATUS_OUT = "host:port"   (where to send heartbeats)
  ST3D_STACK_NAME
  ST3D_SERVICE_NAME
  ST3D_INSTANCE

Versioned wire format (v=1) so we can evolve it.
"""

from __future__ import annotations

import json
import os
import socket
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


def parse_hostport(s: str) -> Tuple[str, int]:
    if not isinstance(s, str) or ":" not in s:
        raise ValueError(f"Invalid host:port: {s!r}")
    host, port_s = s.rsplit(":", 1)
    host = host.strip()
    port = int(port_s.strip())
    return host, port


def env_for_process(
    *,
    stack_name: str,
    service_name: str,
    instance: Optional[str],
    status_out: Optional[str],
) -> Dict[str, str]:
    env: Dict[str, str] = {}
    if stack_name:
        env["ST3D_STACK_NAME"] = str(stack_name)
    if service_name:
        env["ST3D_SERVICE_NAME"] = str(service_name)
    if instance:
        env["ST3D_INSTANCE"] = str(instance)
    if status_out:
        env["ST3D_STATUS_OUT"] = str(status_out)
    return env


@dataclass
class StatusEmitter:
    dst: Tuple[str, int]
    stack: str
    service: str
    instance: str
    pid: int
    min_period_s: float = 0.5
    _sock: socket.socket | None = None
    _last_emit_s: float = 0.0

    @classmethod
    def from_env(
        cls,
        *,
        default_service: str,
        default_instance: str = "",
        min_period_s: float = 0.5,
    ) -> Optional["StatusEmitter"]:
        out = os.getenv("ST3D_STATUS_OUT", "").strip()
        if not out:
            return None
        host, port = parse_hostport(out)
        stack = os.getenv("ST3D_STACK_NAME", "").strip()
        service = os.getenv("ST3D_SERVICE_NAME", default_service).strip() or default_service
        instance = os.getenv("ST3D_INSTANCE", default_instance).strip()
        pid = os.getpid()
        return cls((host, port), stack, service, instance, pid, min_period_s=min_period_s)

    def _ensure_sock(self) -> socket.socket:
        if self._sock is None:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setblocking(False)
            self._sock = s
        return self._sock

    def emit(self, *, level: str = "OK", summary: str = "", fields: Optional[Dict[str, Any]] = None) -> None:
        msg = {
            "v": 1,
            "stack": self.stack,
            "service": self.service,
            "instance": self.instance,
            "pid": self.pid,
            "t_monotonic": time.monotonic(),
            "level": level,
            "summary": summary,
            "fields": fields or {},
        }
        data = json.dumps(msg, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        try:
            self._ensure_sock().sendto(data, self.dst)
        except OSError:
            # best-effort; never crash the process for status telemetry
            return

    def emit_every(self, *, level: str = "OK", summary: str = "", fields: Optional[Dict[str, Any]] = None) -> None:
        now = time.monotonic()
        if (now - self._last_emit_s) < float(self.min_period_s):
            return
        self._last_emit_s = now
        self.emit(level=level, summary=summary, fields=fields)


class StatusCollector:
    def __init__(self, bind: str):
        host, port = parse_hostport(bind)
        self.bind = (host, port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setblocking(False)
        self.sock.bind(self.bind)
        self.last: Dict[Tuple[str, str], Dict[str, Any]] = {}

    def poll(self, *, max_msgs: int = 100) -> int:
        n = 0
        for _ in range(max_msgs):
            try:
                data, _addr = self.sock.recvfrom(4096)
            except BlockingIOError:
                break
            except OSError:
                break
            try:
                msg = json.loads(data.decode("utf-8", errors="replace"))
                if msg.get("v") != 1:
                    continue
                service = str(msg.get("service", ""))
                instance = str(msg.get("instance", ""))
                self.last[(service, instance)] = msg
                n += 1
            except Exception:
                continue
        return n

    def get(self, service: str, instance: str = "") -> Optional[Dict[str, Any]]:
        return self.last.get((service, instance))

    def age_s(self, service: str, instance: str = "") -> Optional[float]:
        msg = self.get(service, instance)
        if not msg:
            return None
        try:
            return time.monotonic() - float(msg.get("t_monotonic", 0.0))
        except Exception:
            return None
