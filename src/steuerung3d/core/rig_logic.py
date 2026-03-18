from __future__ import annotations

from dataclasses import asdict
from typing import Dict, Tuple

from steuerung3d.common.staleness import is_stale
from steuerung3d.core.axis_ids import normalize_axis_id
from steuerung3d.core.core_mode import CoreMode, core_mode_value
from steuerung3d.core.rig_types import RecoverPlan, RigMode, RigSyncConfig
from steuerung3d.core.state import MachineState


def _normalize_rig_mode(value: object) -> RigMode:
    """Accept RigMode, 'DISCOVERY', or 'RigMode.DISCOVERY' and return RigMode.

    This is intentionally tolerant because older code sometimes stringifies enums.
    """
    if isinstance(value, RigMode):
        return value
    if value is None:
        return RigMode.DISCOVERY
    s = str(value).strip()
    if s.startswith("RigMode."):
        s = s.split(".", 1)[1]
    try:
        return RigMode(s)
    except Exception:
        return RigMode.DISCOVERY


def ensure_densi(state: MachineState, device_id: str) -> None:
    device_id = normalize_axis_id(device_id)
    if device_id not in state.densi_registry:
        # state.densi_registry is a first-class field on MachineState
        from steuerung3d.core.rig_types import DensiRuntime

        state.densi_registry[device_id] = DensiRuntime(device_id=device_id)


def note_densi_seen(state: MachineState, device_id: str, *, device_tick: int | None = None) -> None:
    """Mark device as seen this core tick."""
    device_id = normalize_axis_id(device_id)
    ensure_densi(state, device_id)
    d = state.densi_registry[device_id]
    d.last_seen_core_tick = int(state.tick)
    if device_tick is not None:
        d.last_seen_device_tick = int(device_tick)


def densi_online(state: MachineState, device_id: str) -> bool:
    device_id = normalize_axis_id(device_id)
    ensure_densi(state, device_id)
    d = state.densi_registry[device_id]
    timeout = int(state.densi_offline_after_ticks)
    if d.last_seen_core_tick < 0:
        return False
    return not is_stale(int(state.tick), int(d.last_seen_core_tick), int(timeout) + 1)


def frozen(state: MachineState) -> bool:
    rm = _normalize_rig_mode(getattr(state, "rig_mode", RigMode.DISCOVERY))
    return rm in (RigMode.ARMED_SYNC, RigMode.SYNC_ACTIVE, RigMode.SYNC_RECOVER, RigMode.FAULT_SYNC)


def freeze_config(state: MachineState) -> None:
    """Capture a frozen snapshot of participating devices + anchors."""
    reg = state.densi_registry
    participating = [d.device_id for d in reg.values() if bool(d.participating)]
    anchors: Dict[str, Tuple[float, float, float]] = {}
    for dev in participating:
        d = reg[dev]
        if d.anchor_xyz is not None:
            x, y, z = d.anchor_xyz
            anchors[dev] = (float(x), float(y), float(z))
    state.rig_sync_config = RigSyncConfig(
        participating=tuple(sorted(participating)), anchors=anchors
    )


def unfreeze_config(state: MachineState) -> None:
    state.rig_sync_config = RigSyncConfig()


def validate_can_freeze(state: MachineState) -> tuple[bool, str]:
    reg = state.densi_registry
    participating = [d for d in reg.values() if bool(d.participating)]
    if not participating:
        return False, "no participating densis"
    for d in participating:
        if d.anchor_xyz is None:
            return False, f"missing anchor for {d.device_id}"
        if not densi_online(state, d.device_id):
            return False, f"{d.device_id} is offline"
    return True, ""


def capture_last_good(state: MachineState) -> None:
    """Store last-known-good lengths (measured pos) for participating axes."""
    cfg: RigSyncConfig = state.rig_sync_config
    if not cfg.participating:
        return
    lg = state.rig_last_good
    lg["tick"] = int(state.tick)
    lg["lengths"] = {ax: float(state.axes[ax].pos) for ax in cfg.participating if ax in state.axes}


def start_recover_to_last_good(state: MachineState) -> None:
    cfg: RigSyncConfig = state.rig_sync_config
    lg = state.rig_last_good
    lengths = dict(lg.get("lengths", {}) or {})
    rp: RecoverPlan = state.rig_recover_plan
    rp.active = True
    rp.target_lengths = {
        ax: float(lengths.get(ax, 0.0)) for ax in cfg.participating if ax in lengths
    }
    rp.started_tick = int(state.tick)
    if rp.timeout_ticks <= 0:
        rp.timeout_ticks = int(state.rig_recover_timeout_ticks)
    state.rig_recover_plan = rp


def start_resync_now(state: MachineState) -> None:
    # accepting current lengths as new "last good"
    capture_last_good(state)


def stop_recover(state: MachineState) -> None:
    rp: RecoverPlan = state.rig_recover_plan
    rp.active = False
    rp.target_lengths = {}
    state.rig_recover_plan = rp


def enforce_rig_invariants(state: MachineState) -> None:
    """Best-effort rig workflow invariants.

    This function MUST be safe to call every tick. It should never throw.
    """
    rm = _normalize_rig_mode(getattr(state, "rig_mode", RigMode.DISCOVERY))
    state.rig_mode = rm

    # auto transitions
    if rm == RigMode.SYNC_ACTIVE and bool(getattr(state, "estop", False)):
        # freeze stays; move to recover
        state.rig_mode = RigMode.SYNC_RECOVER
        stop_recover(state)
        return

    if rm in (RigMode.ARMED_SYNC, RigMode.SYNC_ACTIVE, RigMode.SYNC_RECOVER):
        cfg: RigSyncConfig = state.rig_sync_config
        # participant offline/fault => FAULT_SYNC
        for dev in cfg.participating:
            if not densi_online(state, dev):
                state.rig_mode = RigMode.FAULT_SYNC
                stop_recover(state)
                return
            ax = state.axes.get(dev)
            if ax is not None and bool(getattr(ax, "fault", False)):
                state.rig_mode = RigMode.FAULT_SYNC
                stop_recover(state)
                return

    if (
        rm == RigMode.SYNC_ACTIVE
        and not bool(getattr(state, "estop", False))
        and not bool(getattr(state, "fault", False))
    ):
        # keep refreshing last_good
        capture_last_good(state)

    # recovery controller
    rm2 = _normalize_rig_mode(getattr(state, "rig_mode", RigMode.DISCOVERY))
    if rm2 != RigMode.SYNC_RECOVER:
        return

    rp: RecoverPlan = state.rig_recover_plan
    if not bool(rp.active):
        return

    # do nothing if safety gate is active
    if bool(getattr(state, "estop", False)) or bool(getattr(state, "fault", False)):
        return

    # ensure we can actually command motion; caller will still clamp by core_mode
    if core_mode_value(getattr(state, "core_mode", "")) != CoreMode.LIVE.value:
        # leave plan armed; UI can enable motion once core_mode is LIVE
        return

    # drive each participating axis toward its target length
    all_done = True
    for axis_id, target in dict(rp.target_lengths).items():
        ax = state.axes.get(axis_id)
        if ax is None:
            continue
        err = float(target) - float(ax.pos)
        if abs(err) > float(rp.tol):
            all_done = False

        cmd = state.ensure_axis_cmd(axis_id)
        cmd.enable = True
        v = float(rp.kp) * err
        vmax = float(rp.v_max)
        if v > vmax:
            v = vmax
        elif v < -vmax:
            v = -vmax
        if abs(err) <= float(rp.tol):
            v = 0.0
        cmd.vel = v

    # optional timeout
    if int(rp.timeout_ticks) > 0 and (int(state.tick) - int(rp.started_tick)) > int(
        rp.timeout_ticks
    ):
        stop_recover(state)
        state.rig_mode = RigMode.FAULT_SYNC
        return

    if all_done:
        stop_recover(state)
        state.rig_mode = RigMode.ARMED_SYNC


def rig_debug_dict(state: MachineState) -> dict[str, object]:
    """Convenience for debugging/telemetry."""
    out: dict[str, object] = {
        "rig_mode": str(_normalize_rig_mode(getattr(state, "rig_mode", RigMode.DISCOVERY))),
        "frozen": frozen(state),
    }
    cfg: RigSyncConfig = getattr(state, "rig_sync_config", RigSyncConfig())
    out["rig_sync_config"] = asdict(cfg)
    rp: RecoverPlan = getattr(state, "rig_recover_plan", RecoverPlan())
    out["recover_plan"] = asdict(rp)
    return out
