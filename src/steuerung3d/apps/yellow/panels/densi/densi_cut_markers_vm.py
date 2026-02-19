"""DenSi cut markers view-model (Qt-free).

This panel is mildly stateful: it updates a 'SystemTime' token while a cut is not latched,
but only advances the token while NOT in ESTOP.

We keep the controller responsible for applying the resulting *effects* to state.params,
so the compute stays testable.
"""

from __future__ import annotations

from dataclasses import dataclass

from ...domain.ui_format import fmt_f_unit


@dataclass(frozen=True)
class CutMarkerEffects:
    # If not None, write to controller._systemtime_tok and state.params["SystemTime"]
    systemtime_tok: str | None = None
    # If not None, write to state.params["PosDiffFor"]
    posdiff_for: float | None = None


@dataclass(frozen=True)
class DenSiCutMarkersVM:
    cut_time_text: str
    cut_pos_text: str
    cut_vel_text: str
    posdiff_text: str
    effects: CutMarkerEffects


def compute_densi_cut_markers_vm(
    *,
    cut_valid: bool,
    estop_now: bool,
    now_token: str,
    systemtime_tok: str | None,
    systemtime_param: str | None,
    cut_pos_m: float | None,
    cut_vel_mps: float | None,
    pos_m: float | None,
) -> DenSiCutMarkersVM:
    # Helper for safe display
    def tok_display(tok: str | None) -> str:
        t = str(tok or "")
        return t if t else "--"

    effects = CutMarkerEffects()

    if not bool(cut_valid):
        # token advances only while NOT in ESTOP
        if estop_now:
            tok = str(systemtime_tok or systemtime_param or "")
            if not tok:
                tok = str(now_token or "")
                effects = CutMarkerEffects(systemtime_tok=tok, posdiff_for=None)
        else:
            tok = str(now_token or "")
            effects = CutMarkerEffects(systemtime_tok=tok, posdiff_for=None)

        return DenSiCutMarkersVM(
            cut_time_text=tok_display(tok),
            cut_pos_text="--",
            cut_vel_text="--",
            posdiff_text="--",
            effects=effects,
        )

    # Latched: show frozen token and captured values
    tok = str(systemtime_tok or systemtime_param or "")
    cut_time_text = tok_display(tok)
    cut_pos_text = fmt_f_unit(float(cut_pos_m or 0.0), "m", ndigits=2)
    cut_vel_text = fmt_f_unit(float(cut_vel_mps or 0.0), "m/s", ndigits=2)

    if pos_m is None:
        return DenSiCutMarkersVM(
            cut_time_text=cut_time_text,
            cut_pos_text=cut_pos_text,
            cut_vel_text=cut_vel_text,
            posdiff_text="--",
            effects=CutMarkerEffects(systemtime_tok=None, posdiff_for=None),
        )

    pd = float(pos_m) - float(cut_pos_m or 0.0)
    return DenSiCutMarkersVM(
        cut_time_text=cut_time_text,
        cut_pos_text=cut_pos_text,
        cut_vel_text=cut_vel_text,
        posdiff_text=fmt_f_unit(pd, "m", ndigits=2),
        effects=CutMarkerEffects(systemtime_tok=None, posdiff_for=pd),
    )
