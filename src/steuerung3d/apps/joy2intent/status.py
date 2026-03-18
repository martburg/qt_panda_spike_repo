from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class Joy2IntentStatusLike(Protocol):
    def emit_every(self, *, level: str, summary: str, fields: dict[str, object]) -> None: ...


@dataclass(frozen=True)
class Joy2IntentStatusPayload:
    level: str
    summary: str
    fields: dict[str, object]


def build_status_payload(
    *,
    mode: str,
    age_ms: float | None,
    stale_stop: bool,
    raw_in: tuple[str, int],
    intent_out: tuple[str, int],
    winches: list[str],
    last_buttons: list[int],
    last_axes: list[float],
    last_axis_pairs: list[str],
    last_selected_axes: list[str],
    last_select_map: list[str],
) -> Joy2IntentStatusPayload:
    stale = (age_ms is not None) and stale_stop
    level = "WARN" if stale else "OK"
    age_ms_i = int(age_ms) if age_ms is not None else None
    btns_s = "[" + ",".join(str(b) for b in last_buttons[:8]) + "]"
    axes_s = "[" + ",".join(f"{a:+.2f}" for a in last_axes[:6]) + "]"
    summary = (
        f"mode={mode} age_ms={age_ms_i if age_ms_i is not None else 'NA'} "
        f"stale_stop={stale_stop} btn={btns_s} axes={axes_s} "
        f"sel={last_selected_axes} map={last_select_map}"
    )
    return Joy2IntentStatusPayload(
        level=level,
        summary=summary,
        fields={
            "mode": mode,
            "age_ms": age_ms_i,
            "stale_stop": stale_stop,
            "raw_in": f"{raw_in[0]}:{raw_in[1]}",
            "intent_out": f"{intent_out[0]}:{intent_out[1]}",
            "winches": list(winches),
            "joy_buttons": list(last_buttons),
            "joy_axes": list(last_axes),
            "joy_axis_pairs": list(last_axis_pairs),
            "selected_axes": list(last_selected_axes),
        },
    )


def emit_status(*, status: Joy2IntentStatusLike, payload: Joy2IntentStatusPayload) -> None:
    status.emit_every(level=payload.level, summary=payload.summary, fields=payload.fields)
