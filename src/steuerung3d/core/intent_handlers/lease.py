from __future__ import annotations

from steuerung3d.core.state import MachineState


def set_lease_denial(state: MachineState, reason: str, req_id: str = "") -> None:
    state.lease_last_denial_reason = str(reason or "")
    if req_id:
        state.core_acks.append(f"{req_id}:deny:{reason}")


def axis_lease_holders(state: MachineState, axis_id: str) -> list[str]:
    holders = getattr(state, "lease_axis_holders", {}) or {}
    vals = holders.get(axis_id, []) if isinstance(holders, dict) else []
    if not isinstance(vals, (list, tuple)):
        return []
    return [str(x) for x in list(vals) if str(x)]


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
    claims = getattr(state, "axis_claims", {}) or {}
    claim = claims.get(str(axis_id or "")) if isinstance(claims, dict) else None
    if not claim:
        return False
    if isinstance(claim, str):
        return claim == hip_id
    return str(getattr(claim, "hip_id", "")) == hip_id
