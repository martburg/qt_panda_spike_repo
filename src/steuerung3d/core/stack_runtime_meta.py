from __future__ import annotations

import os
import time
from typing import TYPE_CHECKING

from .stack_meta import write_meta

if TYPE_CHECKING:
    from .stack_runtime_impl import StackRuntime


def write_runtime_meta(rt: "StackRuntime", *, stopped_at_s: float | None) -> None:
    if rt.session_dir is None:
        return
    meta: dict[str, object] = {
        "stack_name": rt.spec.name,
        "session_dir": str(rt.session_dir),
        "profile_path": str(rt.spec.profile_path) if getattr(rt.spec, "profile_path", None) else "",
        "started_at_s": getattr(rt, "_started_at_s", None) or time.time(),
        "stopped_at_s": stopped_at_s,
        "supervisor_pid": os.getpid(),
        "children": {
            rp.spec.name: {
                "pid": rp.popen.pid,
                "argv": rp.spec.argv,
                "log_path": str(rp.spec.log_path),
                "returncode": rp.popen.poll(),
            }
            for rp in rt.processes
        },
    }
    write_meta(rt.session_dir, meta)
