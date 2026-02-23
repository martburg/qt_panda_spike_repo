"""Run a stack profile as supervised subprocesses.

This is a generalized version of the existing `setup_stack` runner:
- per-process logs in a session directory (with rollover)
- birds-eye view (log tail)
- crash tail of last N lines
- start order and simple dependency hygiene

The runtime consumes a :class:`~steuerung3d.core.stack_spec.StackSpec`.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Dict, List, Optional

from .run_dirs import make_session_dir
from .stack_render import make_context, render_argv
from .stack_spec import ProcessSpec, ServiceSpec, StackSpec
from .stack_meta import write_meta
from .status import StatusCollector, env_for_process


def _birdseye_multiline_default() -> bool:
    return str(os.getenv("BIRDSEYE_MULTILINE", "1")).strip().lower() not in ("0", "false", "no")


def _wrap_line(text: str, width: int) -> list[str]:
    if width <= 0:
        return [text]
    if len(text) <= width:
        return [text]
    out: list[str] = []
    i = 0
    while i < len(text):
        out.append(text[i : i + width])
        i += width
    return out


def format_birds_eye(
    parts: List[str],
    *,
    multiline: bool = True,
    max_entries: int = 6,
    max_width: int = 120,
) -> str:
    if not parts:
        return ""
    items = list(parts[: int(max_entries)])
    if not multiline:
        return "[birds] " + " | ".join(items)

    lines = ["[birds-eye]"]
    prefix = "  - "
    cont = "    "
    wrap_width = max_width - len(prefix)
    for item in items:
        wrapped = _wrap_line(str(item), wrap_width)
        for idx, seg in enumerate(wrapped):
            lines.append(f"{prefix}{seg}" if idx == 0 else f"{cont}{seg}")
    return "\n".join(lines)


def _flag(value: object) -> str:
    if value is True:
        return "1"
    if value is False:
        return "0"
    return "?"


def _age_ms(value: object) -> str:
    if value is None:
        return "?"
    try:
        return str(int(value))
    except Exception:
        return "?"


def _fmt_vel(value: object) -> str:
    if value is None:
        return "?"
    try:
        return f"{float(value):.3f}"
    except Exception:
        return "?"


def build_frederik_panel_lines(fields: Dict[str, object], *, max_blocked: int = 3) -> list[str]:
    if not isinstance(fields, dict):
        return []

    core_mode = str(fields.get("core_mode", fields.get("mode", "")) or "")

    blocked_in = fields.get("blocked_by", [])
    blocked_codes: list[str] = []
    if isinstance(blocked_in, list):
        for item in blocked_in:
            if isinstance(item, dict):
                code = str(item.get("code", ""))
                axis_id = str(item.get("axis_id", ""))
                if axis_id:
                    blocked_codes.append(f"{axis_id}:{code}" if code else axis_id)
                else:
                    blocked_codes.append(code)
            else:
                blocked_codes.append(str(item))
    blocked_codes = [b for b in blocked_codes if b]
    blocked_summary = ",".join(blocked_codes[: int(max_blocked)])

    joy_dm = _flag(fields.get("joy_dm"))
    joy_sel = _flag(fields.get("joy_sel"))
    live_req_seen = _flag(fields.get("live_req_seen"))

    reset_denied = int(fields.get("reset_denied_total", 0) or 0)
    live_denied = int(fields.get("live_denied_count", 0) or 0)
    live_denied_reason = str(fields.get("live_denied_reason", "") or "")
    cmd_estop_reset = _flag(fields.get("cmd_estop_reset"))
    cmd_resync = _flag(fields.get("cmd_resync"))

    lines = [
        f"Frederik: core_mode={core_mode} blocked_by=[{blocked_summary}]",
        f"Frederik: joy_dm={joy_dm} joy_sel={joy_sel} live_req_seen={live_req_seen}",
        f"Frederik: reset_denied={reset_denied} live_denied={live_denied} live_denied_reason={live_denied_reason}",
        f"Frederik: cmd_estop_reset={cmd_estop_reset} cmd_resync={cmd_resync}",
    ]

    axes = fields.get("axes", [])
    if isinstance(axes, list) and axes:
        lines.append("Frederik axes: axis in_scope estop fault started cmd_en cmd_vel taster_enabled armed ready owner age_ms")
        axes_sorted = sorted(axes, key=lambda a: str(a.get("axis_id", "")) if isinstance(a, dict) else str(a))
        for ax in axes_sorted:
            if not isinstance(ax, dict):
                continue
            axis_id = str(ax.get("axis_id", ""))
            in_scope = _flag(ax.get("in_scope"))
            estop = _flag(ax.get("estop"))
            fault = _flag(ax.get("fault"))
            started = _flag(ax.get("started"))
            cmd_enable = _flag(ax.get("cmd_enable"))
            cmd_vel = _fmt_vel(ax.get("cmd_vel"))
            taster = _flag(ax.get("taster_enabled"))
            armed = _flag(ax.get("armed"))
            ready = _flag(ax.get("ready"))
            owner = str(ax.get("owner_hip_id", "") or "-")
            age_ms = _age_ms(ax.get("age_ms"))
            lines.append(
                "Frederik "
                f"axis={axis_id} in_scope={in_scope} estop={estop} fault={fault} "
                f"started={started} cmd_en={cmd_enable} cmd_vel={cmd_vel} taster_enabled={taster} "
                f"armed={armed} ready={ready} "
                f"owner={owner} age_ms={age_ms}"
            )

    return lines


def _now_ts() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def _tail_lines(path: Path, n: int = 40) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    lines = text.splitlines()
    return "\n".join(lines[-n:])


class _LogTailer:
    """Incremental tail reader for a single log file."""

    def __init__(self, path: Path):
        self.path = path
        self._pos = 0
        self.last_line: str = ""

    def poll(self) -> Optional[str]:
        if not self.path.exists():
            return None
        try:
            with self.path.open("r", encoding="utf-8", errors="replace") as f:
                f.seek(self._pos)
                chunk = f.read()
                self._pos = f.tell()
        except Exception:
            return None
        if not chunk:
            return None
        # Update last non-empty line
        for line in chunk.splitlines()[::-1]:
            if line.strip():
                self.last_line = line.strip()
                break
        return self.last_line or None


@dataclass
class RunningProcess:
    spec: ProcessSpec
    popen: subprocess.Popen


def expand_processes(spec: StackSpec, *, session_dir: Path) -> List[ProcessSpec]:
    """Expand services into concrete process specs."""
    stack_ctx = {"name": spec.name}
    rig_ctx = {"axes": spec.axes, **(spec.rig or {})}
    net_ctx = dict(spec.net)

    processes: List[ProcessSpec] = []

    def add_process(name: str, argv: List[str], svc_env: Dict[str, str]):
        log_path = session_dir / f"{name}.log"
        processes.append(ProcessSpec(name=name, argv=argv, log_path=log_path, env=svc_env))

    for svc_key, svc in spec.services.items():
        if not svc.enabled:
            continue
        if not svc.module:
            raise ValueError(f"Service '{svc_key}' has no module")

        if svc.mode == "per_axis":
            for i, axis in enumerate(spec.axes):
                ctx = make_context(stack=stack_ctx, net=net_ctx, rig=rig_ctx, axis=axis, axis_index=i)
                argv = [sys.executable, "-m", svc.module]
                argv += render_argv(_service_args_with_config(svc), ctx)
                add_process(f"{svc_key}-{axis}", argv, dict(svc.env))
        else:
            # Single service instance, or an explicit pool.
            count = getattr(svc, "count", None)
            if isinstance(count, int) and count > 1:
                for i in range(int(count)):
                    ctx = make_context(stack=stack_ctx, net=net_ctx, rig=rig_ctx, axis=None, axis_index=None)
                    argv = [sys.executable, "-m", svc.module]
                    argv += render_argv(_service_args_with_config(svc), ctx)
                    add_process(f"{svc_key}-{i+1}", argv, dict(svc.env))
            else:
                ctx = make_context(stack=stack_ctx, net=net_ctx, rig=rig_ctx, axis=None, axis_index=None)
                argv = [sys.executable, "-m", svc.module]
                argv += render_argv(_service_args_with_config(svc), ctx)
                add_process(svc_key, argv, dict(svc.env))

    return _order_processes(processes)


def _service_args_with_config(svc: ServiceSpec) -> List[object]:
    args: List[object] = list(svc.args)
    if svc.config:
        args = args + ["--config", svc.config]
    return args


def _order_processes(processes: List[ProcessSpec]) -> List[ProcessSpec]:
    """Start-order heuristic.

    Keep it stable and predictable. We prefer core before producers/consumers.
    """
    def rank(name: str) -> int:
        n = name.lower()
        if n.startswith("core"):
            return 10
        if n.startswith("densi") or n.startswith("den"):
            return 20
        if n.startswith("hip"):
            return 30
        if "input" in n:
            return 40
        if "joy" in n:
            return 50
        return 60

    return sorted(processes, key=lambda p: (rank(p.name), p.name))


class StackRuntime:
    def __init__(
        self,
        spec: StackSpec,
        *,
        run_base: Path = Path(".run"),
        keep_last_sessions: int = 5,
        new_console: bool = False,
    ):
        self.spec = spec
        self.run_base = run_base
        self.keep_last_sessions = keep_last_sessions
        self.new_console = bool(new_console)

        self.session_dir: Optional[Path] = None
        self.processes: List[RunningProcess] = []
        self.tailers: Dict[str, _LogTailer] = {}
        self.status: Optional[StatusCollector] = None

    def start(self) -> Path:
        base = self.run_base / self.spec.name
        self.session_dir = make_session_dir(base, keep_last=self.keep_last_sessions)

        status_in = (self.spec.net or {}).get("status_in")
        if status_in:
            try:
                self.status = StatusCollector(bind=str(status_in))
            except Exception:
                self.status = None

        device_source = str((self.spec.rig or {}).get("device_source") or "sim").strip().lower()

        # --- Phase 1: spawn everything except dynamic components ---
        # In REAL mode, PLCs are already running. We start core+tooling first,
        # discover live devices from telemetry, then start a HiP pool.
        spec_for_phase1 = self.spec
        if device_source == "real":
            services = dict(self.spec.services)
            if "densi" in services:
                services["densi"] = replace(services["densi"], enabled=False)
            if "hip" in services:
                services["hip"] = replace(services["hip"], enabled=False)
            spec_for_phase1 = replace(self.spec, services=services)
        else:
            # SIM mode convenience: hip.count="auto" => spawn one HiP per configured axis.
            hip = self.spec.services.get("hip")
            if hip and getattr(hip, "count", None) == "auto":
                services = dict(self.spec.services)
                services["hip"] = replace(hip, count=max(1, len(self.spec.axes)))
                spec_for_phase1 = replace(self.spec, services=services)

        plan = expand_processes(spec_for_phase1, session_dir=self.session_dir)

        for p in plan:
            self._spawn(p)
            time.sleep(0.05)

        # --- Phase 2 (REAL): discover devices then start HiP pool ---
        if device_source == "real" and self.spec.services.get("hip") and self.spec.services["hip"].enabled:
            self._start_hips_real()

        # Write initial metadata for status/log tooling
        self._write_meta(stopped_at_s=None)

        # tailers
        self.tailers = {rp.spec.name: _LogTailer(rp.spec.log_path) for rp in self.processes}
        return self.session_dir

    def _discover_devices(self, *, timeout_s: float) -> List[str]:
        """Discover live device ids from core status heartbeats."""
        if not self.status:
            return []

        deadline = time.time() + max(0.1, float(timeout_s))
        last_devices: List[str] = []
        while time.time() < deadline:
            self.status.poll()
            msg = self.status.get("core", "")
            if msg:
                fields = msg.get("fields", {}) if isinstance(msg, dict) else {}
                devs = fields.get("devices")
                if isinstance(devs, list) and devs:
                    # Normalize to strings.
                    last_devices = [str(x) for x in devs if str(x).strip()]
            time.sleep(0.05)
        # De-dup / stable order.
        out: List[str] = []
        seen = set()
        for d in last_devices:
            if d not in seen:
                seen.add(d)
                out.append(d)
        return out

    def _start_hips_real(self) -> None:
        """REAL-mode HiP provisioning: start a pool sized to discovered devices."""
        assert self.session_dir is not None
        hip = self.spec.services.get("hip")
        if not hip or not hip.enabled:
            return

        discovery_ms = int((self.spec.rig or {}).get("discovery_ms") or 2000)
        devices = self._discover_devices(timeout_s=discovery_ms / 1000.0)

        # Resolve hip.count
        count = getattr(hip, "count", None)
        if isinstance(count, int):
            n_hips = max(1, int(count))
        else:
            # "auto" / None
            n_hips = max(1, len(devices))

        # Start HiPs unattached by default (operator assigns).
        stack_ctx = {"name": self.spec.name}
        rig_ctx = {"axes": self.spec.axes, **(self.spec.rig or {})}
        net_ctx = dict(self.spec.net)

        for i in range(n_hips):
            name = f"hip-{i+1}"
            ctx = make_context(stack=stack_ctx, net=net_ctx, rig=rig_ctx, axis=None, axis_index=None)
            argv = [sys.executable, "-m", hip.module] + render_argv(_service_args_with_config(hip), ctx)
            p = ProcessSpec(name=name, argv=argv, log_path=self.session_dir / f"{name}.log", env=dict(hip.env))
            self._spawn(p)
            time.sleep(0.05)

    def _write_meta(self, *, stopped_at_s: float | None) -> None:
        if self.session_dir is None:
            return
        meta = {
            "stack_name": self.spec.name,
            "session_dir": str(self.session_dir),
            "profile_path": str(self.spec.profile_path) if getattr(self.spec, "profile_path", None) else "",
            "started_at_s": getattr(self, "_started_at_s", None) or time.time(),
            "stopped_at_s": stopped_at_s,
            "supervisor_pid": os.getpid(),
            "children": {
                rp.spec.name: {
                    "pid": rp.popen.pid,
                    "argv": rp.spec.argv,
                    "log_path": str(rp.spec.log_path),
                    "returncode": rp.popen.poll(),
                }
                for rp in self.processes
            },
        }
        write_meta(self.session_dir, meta)

    def _spawn(self, p: ProcessSpec):
        assert self.session_dir is not None
        p.log_path.parent.mkdir(parents=True, exist_ok=True)
        log_f = p.log_path.open("w", encoding="utf-8")

        env = os.environ.copy()

        # Inject structured-status env so children can emit heartbeats (side-channel).
        # Children should send heartbeats to the supervisor's status_in bind.
        status_out = (self.spec.net or {}).get("status_in")
        if status_out:
            svc_name, inst = (p.name.split("-", 1) + [""])[:2]
            env.update(
                env_for_process(
                    stack_name=self.spec.name,
                    service_name=svc_name,
                    instance=inst,
                    status_out=str(status_out),
                )
            )
        # Preserve per-process environment additions (ports, endpoints, etc.).
        env.update(p.env or {})

        popen_kwargs = dict(stdout=log_f, stderr=subprocess.STDOUT, cwd=str(self.spec.base_dir), env=env)
        if self.new_console and os.name == "nt":
            # Best-effort: create a new console window for each child.
            # (Used for debugging on Windows; no-op on other platforms.)
            popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)

        proc = subprocess.Popen(p.argv, **popen_kwargs)
        # keep file handle alive by attaching it
        proc._stack_log_fh = log_f  # type: ignore[attr-defined]
        self.processes.append(RunningProcess(spec=p, popen=proc))

    def run_forever(self) -> int:
        """Run until Ctrl+C or a child exits. Returns exit code."""
        birds_next = time.time() + 1.0
        last_birds = ""
        try:
            while True:
                # check exits
                for rp in list(self.processes):
                    rc = rp.popen.poll()
                    if rc is not None:
                        self._report_crash(rp, rc)
                        return rc if rc != 0 else 0

                now = time.time()
                if now >= birds_next:
                    birds_next = now + 1.0
                    line = self._birds_eye_line()
                    if line and line != last_birds:
                        print(line)
                        last_birds = line

                time.sleep(0.2)
        except KeyboardInterrupt:
            return 0
        finally:
            self.stop()

    def _birds_eye_line(self) -> str:
        parts: List[str] = []

        # Prefer structured status heartbeats when available.
        if self.status:
            self.status.poll()
            for rp in self.processes:
                svc, inst = (rp.spec.name.split("-", 1) + [""])[:2]
                sm = self.status.get(svc, inst)
                if sm:
                    age = self.status.age_s(svc, inst)
                    age_ms = int((age or 0.0) * 1000.0)
                    # StatusCollector may return either a small dataclass-like object
                    # or a plain dict (depending on import boundaries / older callers).
                    if isinstance(sm, dict):
                        level = str(sm.get("level", ""))
                        summary = str(sm.get("summary", ""))
                        fields = sm.get("fields", {}) if isinstance(sm.get("fields", {}), dict) else {}
                    else:
                        level = str(getattr(sm, "level", ""))
                        summary = str(getattr(sm, "summary", ""))
                        fields = {}
                    parts.append(f"{rp.spec.name}: {level} {summary} ({age_ms}ms)")
                    if isinstance(fields, dict) and str(fields.get("component", "")) == "core":
                        parts.extend(build_frederik_panel_lines(fields))
                else:
                    t = self.tailers.get(rp.spec.name)
                    if t:
                        t.poll()
                        if t.last_line:
                            parts.append(f"{rp.spec.name}: {t.last_line[:120]}")
        else:
            for name, t in self.tailers.items():
                t.poll()
                if t.last_line:
                    parts.append(f"{name}: {t.last_line[:120]}")
        has_frederik = any(str(p).startswith("Frederik") for p in parts)
        max_entries = max(6, len(parts)) if has_frederik else 6
        return format_birds_eye(parts, multiline=_birdseye_multiline_default(), max_entries=max_entries)

    def _report_crash(self, rp: RunningProcess, rc: int):
        print(f"\n[stack] process exited: {rp.spec.name} pid={rp.popen.pid} rc={rc}")
        print(f"[stack] log: {rp.spec.log_path}")
        tail = _tail_lines(rp.spec.log_path, 40)
        if tail:
            print("[stack] --- last 40 lines ---")
            print(tail)
            print("[stack] ---------------------")

    def stop(self):
        # terminate children
        for rp in self.processes:
            try:
                if rp.popen.poll() is None:
                    rp.popen.terminate()
            except Exception:
                pass

        deadline = time.time() + 1.5
        for rp in self.processes:
            try:
                timeout = max(0.0, deadline - time.time())
                rp.popen.wait(timeout=timeout)
            except Exception:
                pass

        # close log handles
        for rp in self.processes:
            fh = getattr(rp.popen, "_stack_log_fh", None)
            try:
                if fh:
                    fh.close()
            except Exception:
                pass

        # final metadata snapshot
        try:
            self._write_meta(stopped_at_s=time.time())
        except Exception:
            pass

        # final metadata snapshot
        try:
            self._write_meta(stopped_at_s=time.time())
        except Exception:
            pass