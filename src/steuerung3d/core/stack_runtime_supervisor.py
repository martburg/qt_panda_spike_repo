from __future__ import annotations

import os
import subprocess
import time
from typing import IO, TYPE_CHECKING, List, cast

from steuerung3d.ui.birdseye_format import (
    BirdsEyeFields,
    birdseye_multiline_default,
    build_frederik_panel_lines,
    format_birds_eye,
    tail_lines,
)

from .stack_preflight import cleanup_residual_bind_ports, extract_bind_ports
from .stack_runtime_meta import write_runtime_meta
from .status import env_for_process


def _as_object_dict(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    mapping = cast(dict[object, object], value)
    return {str(k): v for k, v in mapping.items()}


if TYPE_CHECKING:
    from .stack_runtime_impl import RunningProcess, StackRuntime
    from .stack_spec import ProcessSpec


def spawn_process(rt: "StackRuntime", p: "ProcessSpec") -> None:
    assert rt.session_dir is not None
    p.log_path.parent.mkdir(parents=True, exist_ok=True)
    log_f = p.log_path.open("w", encoding="utf-8")

    env = os.environ.copy()
    status_out = (rt.spec.net or {}).get("status_in")
    if status_out:
        svc_name, inst = (p.name.split("-", 1) + [""])[:2]
        env.update(
            env_for_process(
                stack_name=rt.spec.name,
                service_name=svc_name,
                instance=inst,
                status_out=str(status_out),
            )
        )
    env.update(p.env or {})

    if rt.new_console and os.name == "nt":
        proc: subprocess.Popen[bytes] = subprocess.Popen(
            p.argv,
            stdout=log_f,
            stderr=subprocess.STDOUT,
            cwd=str(rt.spec.base_dir),
            env=env,
            creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
        )
    else:
        proc: subprocess.Popen[bytes] = subprocess.Popen(
            p.argv,
            stdout=log_f,
            stderr=subprocess.STDOUT,
            cwd=str(rt.spec.base_dir),
            env=env,
        )
    proc._stack_log_fh = log_f  # type: ignore[attr-defined]
    from .stack_runtime_impl import RunningProcess

    rt.processes.append(RunningProcess(spec=p, popen=proc))


def birds_eye_line(rt: "StackRuntime") -> str:
    parts: List[str] = []
    if rt.status:
        rt.status.poll()
        for rp in rt.processes:
            svc, inst = (rp.spec.name.split("-", 1) + [""])[:2]
            sm = rt.status.get(svc, inst)
            if sm:
                age = rt.status.age_s(svc, inst)
                age_ms = int((age or 0.0) * 1000.0)
                sm_dict = _as_object_dict(sm)
                level = str(sm_dict.get("level", ""))
                summary = str(sm_dict.get("summary", ""))
                fields = _as_object_dict(sm_dict.get("fields", {}))
                parts.append(f"{rp.spec.name}: {level} {summary} ({age_ms}ms)")
                if str(fields.get("component", "")) == "core":
                    parts.extend(build_frederik_panel_lines(cast(BirdsEyeFields, fields)))
            else:
                t = rt.tailers.get(rp.spec.name)
                if t:
                    t.poll()
                    if t.last_line:
                        parts.append(f"{rp.spec.name}: {t.last_line[:120]}")
    else:
        for name, t in rt.tailers.items():
            t.poll()
            if t.last_line:
                parts.append(f"{name}: {t.last_line[:120]}")
    has_frederik = any(str(p).startswith("Frederik") for p in parts)
    max_entries = max(6, len(parts)) if has_frederik else 6
    return format_birds_eye(parts, multiline=birdseye_multiline_default(), max_entries=max_entries)


def report_crash(rt: "StackRuntime", rp: "RunningProcess", rc: int) -> None:
    print(f"\n[stack] process exited: {rp.spec.name} pid={rp.popen.pid} rc={rc}")
    print(f"[stack] log: {rp.spec.log_path}")
    tail = tail_lines(rp.spec.log_path, 40)
    if tail:
        print("[stack] --- last 40 lines ---")
        print(tail)
        print("[stack] ---------------------")


def run_forever(rt: "StackRuntime") -> int:
    birds_next = time.time() + 1.0
    last_birds = ""
    try:
        while True:
            for rp in list(rt.processes):
                rc = rp.popen.poll()
                if rc is not None:
                    report_crash(rt, rp, rc)
                    return rc if rc != 0 else 0

            now = time.time()
            if now >= birds_next:
                birds_next = now + 1.0
                line = birds_eye_line(rt)
                if line and line != last_birds:
                    print(line)
                    last_birds = line

            time.sleep(0.2)
    except KeyboardInterrupt:
        return 0
    finally:
        stop_runtime(rt)


def stop_runtime(rt: "StackRuntime") -> None:
    bind_ports = extract_bind_ports([rp.spec for rp in rt.processes])

    for rp in rt.processes:
        try:
            if rp.popen.poll() is None:
                rp.popen.terminate()
        except Exception:
            pass

    deadline = time.time() + 1.5
    for rp in rt.processes:
        try:
            timeout = max(0.0, deadline - time.time())
            rp.popen.wait(timeout=timeout)
        except Exception:
            pass

    for rp in rt.processes:
        try:
            if rp.popen.poll() is None:
                rp.popen.kill()
        except Exception:
            pass

    deadline = time.time() + 1.0
    for rp in rt.processes:
        try:
            timeout = max(0.0, deadline - time.time())
            rp.popen.wait(timeout=timeout)
        except Exception:
            pass

    try:
        if rt.status is not None:
            rt.status.sock.close()
    except Exception:
        pass

    cleanup_residual_bind_ports(bind_ports)

    for rp in rt.processes:
        fh = cast(IO[str] | None, getattr(rp.popen, "_stack_log_fh", None))
        try:
            if fh:
                fh.close()
        except Exception:
            pass

    try:
        write_runtime_meta(rt, stopped_at_s=time.time())
    except Exception:
        pass
