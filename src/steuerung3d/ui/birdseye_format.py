"""Birds-eye formatting helpers for the stack supervisor.

These utilities are UI-ish (presentation only) but intentionally have no UI
framework dependencies.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


def birdseye_multiline_default() -> bool:
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
        lines.append(
            "Frederik axes: axis in_scope estop fault started cmd_en cmd_vel taster_enabled armed ready owner age_ms"
        )
        axes_sorted = sorted(
            axes, key=lambda a: str(a.get("axis_id", "")) if isinstance(a, dict) else str(a)
        )
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


def tail_lines(path: Path, n: int = 40) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    lines = text.splitlines()
    return "\n".join(lines[-n:])


@dataclass
class LogTailer:
    """Incremental tail reader for a single log file."""

    path: Path
    _pos: int = 0
    last_line: str = ""

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
        for line in chunk.splitlines()[::-1]:
            if line.strip():
                self.last_line = line.strip()
                break
        return self.last_line or None
