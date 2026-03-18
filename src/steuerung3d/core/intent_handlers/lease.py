from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from steuerung3d.core.state import MachineState


def _as_object_map(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        return {}
    mapping = cast(Mapping[object, object], value)
    return {str(k): v for k, v in mapping.items()}


def set_lease_denial(state: MachineState, reason: str, req_id: str = "") -> None:
    state.lease_last_denial_reason = str(reason or "")
    if req_id:
        state.core_acks.append(f"{req_id}:deny:{reason}")


def axis_lease_holders(state: MachineState, axis_id: str) -> list[str]:
    holders = _as_object_map(getattr(state, "lease_axis_holders", {}) or {})
    vals_obj = holders.get(axis_id, [])
    if not isinstance(vals_obj, (list, tuple)):
        return []
    vals = cast(list[object] | tuple[object, ...], vals_obj)
    return [str(x) for x in vals if str(x)]


def axis_lease_allows(state: MachineState, axis_id: str, hip_id: str) -> bool:
    """Return whether *hip_id* may send control intents for *axis_id*.

    We support two related concepts:
      1) **lease holders** (future / multi-HiP arbitration)
      2) **claim owner** (legacy behaviour; a DenSi locks to one controlling HiP)

    Some profiles currently set the claim but do not populate lease holders.
    Without this fallback, *all* EnableAxis/JogWinch intents are rejected, so
    cmd_en/cmd_vel stay at zero even though the joystick is active.
    """

    hip_id = str(hip_id or "")
    holders = axis_lease_holders(state, axis_id)
    if holders and hip_id in holders:
        return True

    # Fallback to legacy claim owner if present.
    claims = _as_object_map(getattr(state, "axis_claims", {}) or {})
    claim = claims.get(str(axis_id or ""))
    if not claim:
        return False
    if isinstance(claim, str):
        return claim == hip_id
    return str(getattr(claim, "hip_id", "")) == hip_id


def axis_lease_allows_any(state: MachineState, axis_id: str) -> bool:
    """Return whether *axis_id* is controlled by *someone*.

    This is used when building the outbound CommandFrame for devices/DenSi.

    Rationale: Some profiles establish an axis claim (legacy ownership) but do
    not yet populate lease holders (multi-HiP arbitration). If we require lease
    holders strictly, the CommandFrame will disable all axes and DenSi will
    never see control words / velocities.

    Policy (device-facing):
      - If lease holders exist for an axis -> allow.
      - Else if an axis claim exists -> allow (legacy behaviour).
    """

    axis_id = str(axis_id or "")
    if not axis_id:
        return False

    holders = axis_lease_holders(state, axis_id)
    if holders:
        return True

    claims = _as_object_map(getattr(state, "axis_claims", {}) or {})
    if axis_id in claims and claims.get(axis_id) is not None:
        return True

    return False
