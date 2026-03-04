"""Qt-free DenSi parameter op application.

This is the device-side mirror of the v0.1 param-edit protocol used by HiP.
DenSi semantics to preserve:
- Guard policy is computed by the controller; if allow=False, ops are ignored.
- ParamEditBegin: activates session for group
- ParamCancel: clears session (if group matches or group="")
- ParamWrite:
    * normalize group-specific values before session checks
    * reject writes if a different group session is active
    * enforce device-side ranges after session check
    * update state.params and end session after successful write

This module does not touch Qt.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

from steuerung3d.core.state import MachineState


@dataclass(frozen=True)
class DenSiParamOpsResult:
    applied_values: dict[str, float]


def apply_densi_param_ops(
    *,
    state: MachineState,
    # Accept both canonical ParamOp objects and legacy JSON-like dicts.
    # coerce_param_ops performs the tolerance/cleaning.
    param_ops: Sequence[object] | None,
    allow: bool,
    normalize_pos_chain: Callable[[Mapping[str, float]], dict[str, float]],
    normalize_guider_range: Callable[[Mapping[str, float]], dict[str, float]],
    enforce_pos_chain: Callable[[Mapping[str, float]], dict[str, float]],
    enforce_guider_minmax: Callable[[Mapping[str, float]], dict[str, float]],
) -> DenSiParamOpsResult:
    """Apply parameter ops to state.

    normalize_* / enforce_* are callables from DenSiController (keeps semantics).
    """

    applied: dict[str, float] = {}

    # Import here to keep module import side-effects minimal and avoid cycles.
    from steuerung3d.core.command_frame import (
        ParamCancelOp,
        ParamEditBeginOp,
        ParamWriteOp,
        coerce_param_ops,
    )

    for op in coerce_param_ops(list(param_ops or [])):
        if not allow:
            continue

        if isinstance(op, ParamEditBeginOp):
            grp = str(op.group or "")
            state.param_edit_active = True
            state.param_edit_group = grp

        elif isinstance(op, ParamCancelOp):
            grp = str(op.group or "")
            if (not grp) or (grp == state.param_edit_group):
                state.param_edit_active = False
                state.param_edit_group = ""

        elif isinstance(op, ParamWriteOp):
            grp = str(op.group or "")
            vals = {str(k): float(v) for k, v in dict(op.values or {}).items()}

            # normalize first (matches controller semantics)
            if grp == "pos":
                vals = normalize_pos_chain(vals)
            elif grp == "guider":
                vals = normalize_guider_range(vals)

            if state.param_edit_active and (grp != state.param_edit_group):
                # reject mismatched active session
                continue

            if grp == "pos":
                vals = enforce_pos_chain(vals)
            elif grp == "guider":
                vals = enforce_guider_minmax(vals)

            state.params.update(vals)
            applied.update(vals)

            # end edit session after a successful write
            state.param_edit_active = False
            state.param_edit_group = ""

    return DenSiParamOpsResult(applied_values=applied)
