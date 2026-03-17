from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from steuerung3d.apps.yellow.domain.banner_facts import derive_banner_estate_from_word
from steuerung3d.core.executor import build_command_frame
from steuerung3d.core.state import MachineState
from steuerung3d.protocol.estop_bits import decode_estop_word

from .birds_eye_types import (
    BirdsEyeAxisDetailStateLike,
    BirdsEyeRouterLike,
    BirdsEyeSnapLike,
    CommandFrameLike,
)


@dataclass(frozen=True)
class _StaticAxisCommandOut:
    enable: bool = False
    vel: float = 0.0


@dataclass(frozen=True)
class _StaticCommandFrame:
    axes: Mapping[str, _StaticAxisCommandOut]
    estop_reset: bool = False
    resync: bool = False


def _as_mapping(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        return {}
    result: dict[str, object] = {}
    for key, item in value.items():
        result[str(key)] = item
    return result


def _build_blocked_payload(
    state: BirdsEyeAxisDetailStateLike,
) -> tuple[list[str], list[dict[str, object]]]:
    blocked_by: list[str] = []
    blocked_payload: list[dict[str, object]] = []
    core_blocked = list(state.core_blocked_by or [])
    for item in core_blocked:
        code = str(getattr(item, "code", item))
        axis_id = getattr(item, "axis_id", None)
        detail = getattr(item, "detail", None)
        blocked_by.append(f"{axis_id}:{code}" if axis_id else code)
        blocked_payload.append({"code": code, "axis_id": axis_id, "detail": detail})
    return blocked_by, blocked_payload


def _decode_estop_state(
    *, router: BirdsEyeRouterLike | None, snap: BirdsEyeSnapLike, axis_id: str
) -> tuple[dict[str, object], str]:
    last_dev_estop_word_by_axis = router.last_dev_estop_word_by_axis if router is not None else {}
    estop_word = int(last_dev_estop_word_by_axis.get(axis_id, int(snap.estop_status_word)) or 0)
    try:
        bits = decode_estop_word(estop_word)
        estate = derive_banner_estate_from_word(estop_word, within_brake_grace=lambda: False)
        typed_bits: dict[str, object] = {str(key): value for key, value in bits.items()}
        return typed_bits, estate
    except Exception:
        return {}, ""


def _resolve_axis_owner(*, state: BirdsEyeAxisDetailStateLike, axis_id: str) -> str:
    owner = str(state.claim_owner(axis_id) or "")
    if owner:
        return owner
    holders = list(state.lease_axis_holders.get(axis_id, []) or [])
    return str(holders[0]) if holders else ""


def _build_command_frame_for_birdseye(state: BirdsEyeAxisDetailStateLike) -> CommandFrameLike:
    if isinstance(state, MachineState):
        return build_command_frame(state)

    axes: dict[str, _StaticAxisCommandOut] = {}
    for axis_id, cmd in state.axis_cmd.items():
        axis_name = str(axis_id).strip()
        if not axis_name:
            continue
        try:
            vel = float(getattr(cmd, "vel", 0.0) or 0.0)
        except Exception:
            vel = 0.0
        axes[axis_name] = _StaticAxisCommandOut(
            enable=bool(getattr(cmd, "enable", False)),
            vel=vel,
        )
    return _StaticCommandFrame(axes=axes)


def _build_axis_snapshot_entry(
    *,
    axis_id: str,
    snap: BirdsEyeSnapLike,
    state: BirdsEyeAxisDetailStateLike,
    router: BirdsEyeRouterLike | None,
    cmd_axes: Mapping[str, object],
    axis_cmd: Mapping[str, object],
    axis_gate: Mapping[str, object],
) -> dict[str, object]:
    bits, estate = _decode_estop_state(router=router, snap=snap, axis_id=axis_id)
    estate_upper = str(estate).upper()
    armed = estate_upper in ("ARMED", "READY")
    ready = estate_upper == "READY"

    cmd = axis_cmd.get(axis_id)
    cmd_out = cmd_axes.get(axis_id)
    cmd_enable = None
    cmd_vel = None
    if cmd_out is not None:
        cmd_enable = bool(getattr(cmd_out, "enable", False))
        try:
            cmd_vel = float(getattr(cmd_out, "vel", 0.0) or 0.0)
        except Exception:
            cmd_vel = 0.0

    started = bool(
        cmd
        and (
            bool(getattr(cmd, "enable", False)) or abs(float(getattr(cmd, "vel", 0.0) or 0.0)) > 0.0
        )
    )

    owner = _resolve_axis_owner(state=state, axis_id=axis_id)
    reset_allowed = bool(owner) and bool(bits.get("reset_able", False))
    estop_axis = estate_upper == "ESTOP"
    fault_axis = bool(state.fault)

    gate = dict(_as_mapping(axis_gate.get(axis_id, {})))
    gate_estop = gate.get("hard_estop_active")
    gate_fault = gate.get("fault_estop_active")
    gate_taster = gate.get("taster")
    gate_armed = gate.get("armed")
    gate_ready = gate.get("ready")
    gate_owner = gate.get("owner")
    gate_age_ms = gate.get("age_ms")
    gate_key_mode = gate.get("key_mode")
    if gate_owner:
        owner = str(gate_owner)

    estop_axis = bool(gate_estop) if gate_estop is not None else estop_axis
    fault_axis = bool(gate_fault) if gate_fault is not None else fault_axis
    armed = bool(gate_armed) if gate_armed is not None else bool(armed)
    ready = bool(gate_ready) if gate_ready is not None else bool(ready)

    return {
        "axis_id": str(axis_id),
        "in_scope": bool(gate.get("in_scope", True)),
        "key_mode": str(gate_key_mode or ""),
        "estop": bool(estop_axis),
        "fault": bool(fault_axis),
        "started": bool(started),
        "cmd_enable": cmd_enable,
        "cmd_vel": cmd_vel,
        "taster_enabled": gate_taster,
        "armed": bool(armed),
        "ready": bool(ready),
        "owner_hip_id": str(owner or ""),
        "age_ms": gate_age_ms,
        "reset_allowed": bool(reset_allowed),
    }


def build_blocked_and_axes_snapshot(
    *,
    snap: BirdsEyeSnapLike,
    state: BirdsEyeAxisDetailStateLike,
    router: BirdsEyeRouterLike | None,
    axis_ids: list[str],
) -> tuple[list[dict[str, object]], list[str], list[dict[str, object]], CommandFrameLike]:
    """Build per-axis status + blocked-by summary for birds-eye reporting."""
    cmd_frame = _build_command_frame_for_birdseye(state)
    cmd_axes = _as_mapping(cmd_frame.axes)
    blocked_by, blocked_payload = _build_blocked_payload(state)
    axis_cmd = _as_mapping(state.axis_cmd)
    axis_gate = _as_mapping(state.core_axis_gate)
    axes_snapshot = [
        _build_axis_snapshot_entry(
            axis_id=axis_id,
            snap=snap,
            state=state,
            router=router,
            cmd_axes=cmd_axes,
            axis_cmd=axis_cmd,
            axis_gate=axis_gate,
        )
        for axis_id in axis_ids
    ]
    return axes_snapshot, blocked_by, blocked_payload, cmd_frame
