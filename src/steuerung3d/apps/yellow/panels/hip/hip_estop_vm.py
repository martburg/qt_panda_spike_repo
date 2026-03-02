"""HiP estop view-model (Qt-free)."""

from __future__ import annotations

from typing import Any, Callable, Mapping

from steuerung3d.protocol.estop_bits import ESTOP_SPECS

from ...domain.ui_estop import active_estop_keys_for_profile, compute_estop_dot_states
from ...engines.hip.viewmodel import HipEstopState


def compute_hip_estop_vm(
    *,
    logical: Mapping[str, Any],
    taster: bool,
    attached: bool,
    brake_ok_display: Callable[[bool], bool],
    profile: object,
    prev_profile: str,
) -> HipEstopState:
    active_keys = active_estop_keys_for_profile(profile, ESTOP_SPECS.keys())
    profile_changed = str(profile) != str(prev_profile or "")

    estop_dots = compute_estop_dot_states(
        bits=dict(logical),
        taster=bool(taster),
        specs=ESTOP_SPECS.values(),
        brake_ok_display=brake_ok_display,
    )
    checkbox_states = {spec.key: bool(dict(logical).get(spec.key, False)) for spec in ESTOP_SPECS.values()}
    reset_enabled = bool(dict(logical).get("reset_able", False)) if attached else False

    return HipEstopState(
        dots=estop_dots,
        reset_enabled=bool(reset_enabled),
        checkbox_states=checkbox_states,
        active_keys=set(active_keys),
        profile_changed=bool(profile_changed),
    )
