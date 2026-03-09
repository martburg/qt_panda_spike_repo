from __future__ import annotations

from typing import Mapping

from steuerung3d.core.telemetry import TelemetrySnapshot
from steuerung3d.protocol.estop_bits import decode_estop_word

from ...domain.ui_format import fmt_f_unit
from .presentation_extract import parse_estop_word_from_snapshot, raw_tail_token
from .viewmodel import HipCutMarkersState


def compute_cut_markers_state(
    *,
    snap: TelemetrySnapshot,
    params: Mapping[str, float],
    estate: str,
    mode: str,
) -> HipCutMarkersState:
    try:
        cut_pos = float(params.get("CutPos", 0.0) or 0.0)
        cut_vel = float(params.get("CutVel", 0.0) or 0.0)
        posdiff = float(params.get("PosDiffFor", 0.0) or 0.0)
    except Exception:
        cut_pos = 0.0
        cut_vel = 0.0
        posdiff = 0.0

    in_estop = bool(getattr(snap, "estop", False))
    try:
        word = parse_estop_word_from_snapshot(snap)
        bits = decode_estop_word(int(word))
        in_estop = any(
            bool(bits.get(k, False)) for k in ("master", "slave", "network", "estop1", "estop2")
        )
    except Exception:
        pass
    if not in_estop and str(estate or "").upper() == "ESTOP":
        in_estop = True
    mode_u = str(mode or "").upper()
    in_sync = mode_u.startswith("SYNC")

    if in_sync:
        cut_pos_text = "--"
        cut_vel_text = "--"
        posdiff_text = "--"
    else:
        cut_pos_text = fmt_f_unit(cut_pos, "m", ndigits=2)
        cut_vel_text = fmt_f_unit(cut_vel, "m/s", ndigits=2)
        posdiff_text = fmt_f_unit(posdiff, "m", ndigits=2)

    t_tok = raw_tail_token(snap, "SystemTime")
    cut_time_text = t_tok if t_tok else "--"
    return HipCutMarkersState(
        cut_time_text=str(cut_time_text),
        cut_pos_text=str(cut_pos_text),
        cut_vel_text=str(cut_vel_text),
        posdiff_text=str(posdiff_text),
    )
