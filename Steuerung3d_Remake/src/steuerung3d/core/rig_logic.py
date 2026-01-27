from __future__ import annotations

from dataclasses import asdict
from typing import Dict, Iterable, Tuple

from steuerung3d.core.state import MachineState
from steuerung3d.core.rig_types import RigMode, RigSyncConfig, RecoverPlan


def ensure_densi(state: MachineState, device_id: str) -> None:
    if not hasattr(state, 'densi_registry'):
        state.densi_registry = {}
    if device_id not in state.densi_registry:
        # lazy import to avoid circulars
        from steuerung3d.core.rig_types import DensiRuntime
        state.densi_registry[device_id] = DensiRuntime(device_id=device_id)


def note_densi_seen(state: MachineState, device_id: str, *, device_tick: int | None = None) -> None:
    """Mark device as seen this core tick."""
    ensure_densi(state, device_id)
    d = state.densi_registry[device_id]
    d.last_seen_core_tick = int(state.tick)
    if device_tick is not None:
        d.last_seen_device_tick = int(device_tick)


def densi_online(state: MachineState, device_id: str) -> bool:
    ensure_densi(state, device_id)
    d = state.densi_registry[device_id]
    timeout = int(getattr(state, 'densi_offline_after_ticks', 40))
    if d.last_seen_core_tick < 0:
        return False
    return (int(state.tick) - int(d.last_seen_core_tick)) <= timeout


def frozen(state: MachineState) -> bool:
    rm = getattr(state, 'rig_mode', RigMode.DISCOVERY)
    try:
        rm = RigMode(str(rm))
    except Exception:
        rm = RigMode.DISCOVERY
    return rm in (RigMode.ARMED_SYNC, RigMode.SYNC_ACTIVE, RigMode.SYNC_RECOVER, RigMode.FAULT_SYNC)


def freeze_config(state: MachineState) -> None:
    """Capture a frozen snapshot of participating devices + anchors."""
    if not hasattr(state, 'rig_sync_config'):
        state.rig_sync_config = RigSyncConfig()
    reg = getattr(state, 'densi_registry', {})
    participating = [d.device_id for d in reg.values() if bool(d.participating)]
    anchors: Dict[str, Tuple[float, float, float]] = {}
    for dev in participating:
        d = reg[dev]
        if d.anchor_xyz is not None:
            anchors[dev] = tuple(float(x) for x in d.anchor_xyz)
    state.rig_sync_config = RigSyncConfig(participating=tuple(sorted(participating)), anchors=anchors)


def unfreeze_config(state: MachineState) -> None:
    state.rig_sync_config = RigSyncConfig()


def validate_can_freeze(state: MachineState) -> tuple[bool, str]:
    reg = getattr(state, 'densi_registry', {})
    participating = [d for d in reg.values() if bool(d.participating)]
    if not participating:
        return False, 'no participating densis'
    for d in participating:
        if d.anchor_xyz is None:
            return False, f'missing anchor for {d.device_id}'
        if not densi_online(state, d.device_id):
            return False, f'{d.device_id} is offline'
    return True, ''


def capture_last_good(state: MachineState) -> None:
    """Store last-known-good lengths (measured pos) for participating axes."""
    cfg: RigSyncConfig = getattr(state, 'rig_sync_config', RigSyncConfig())
    if not cfg.participating:
        return
    lg = {}
    for axis_id in cfg.participating:
        ax = state.axes.get(axis_id)
        if ax is None:
            continue
        lg[axis_id] = float(ax.pos)
    state.rig_last_good_lengths = lg
    state.rig_last_good_tick = int(state.tick)


def start_recover_to_last_good(state: MachineState) -> None:
    """Plan a recovery move back to last_good_lengths."""
    target = dict(getattr(state, 'rig_last_good_lengths', {}))
    if not hasattr(state, 'rig_recover_plan'):
        state.rig_recover_plan = RecoverPlan()
    rp: RecoverPlan = state.rig_recover_plan
    rp.active = True
    rp.target_lengths = target
    rp.started_tick = int(state.tick)


def stop_recover(state: MachineState) -> None:
    if hasattr(state, 'rig_recover_plan'):
        state.rig_recover_plan.active = False
        state.rig_recover_plan.target_lengths = {}


def enforce_rig_invariants(state: MachineState) -> None:
    """Per-tick rig logic.

    Called every tick from the core engine before the command frame is built.
    """
    # bootstrap defaults
    if not hasattr(state, 'rig_mode'):
        state.rig_mode = RigMode.DISCOVERY
    if not hasattr(state, 'densi_registry'):
        state.densi_registry = {}
    if not hasattr(state, 'rig_sync_config'):
        state.rig_sync_config = RigSyncConfig()
    if not hasattr(state, 'rig_recover_plan'):
        state.rig_recover_plan = RecoverPlan()

    try:
        rm = RigMode(str(state.rig_mode))
    except Exception:
        rm = RigMode.DISCOVERY
        state.rig_mode = rm

    # auto transitions
    if rm == RigMode.SYNC_ACTIVE and bool(state.estop):
        # freeze stays; move to recover
        state.rig_mode = RigMode.SYNC_RECOVER
        stop_recover(state)
        return

    if rm in (RigMode.ARMED_SYNC, RigMode.SYNC_ACTIVE, RigMode.SYNC_RECOVER):
        cfg: RigSyncConfig = getattr(state, 'rig_sync_config', RigSyncConfig())
        # participant offline/fault => FAULT_SYNC
        for dev in cfg.participating:
            if not densi_online(state, dev):
                state.rig_mode = RigMode.FAULT_SYNC
                stop_recover(state)
                return
            ax = state.axes.get(dev)
            if ax is not None and bool(getattr(ax, 'fault', False)):
                state.rig_mode = RigMode.FAULT_SYNC
                stop_recover(state)
                return

    if rm == RigMode.SYNC_ACTIVE and not bool(state.estop) and not bool(state.fault):
        # keep refreshing last_good
        capture_last_good(state)

    # recovery controller
    rm = RigMode(str(getattr(state, 'rig_mode')))
    if rm != RigMode.SYNC_RECOVER:
        return

    rp: RecoverPlan = getattr(state, 'rig_recover_plan', RecoverPlan())
    if not bool(rp.active):
        return

    # do nothing if safety gate is active
    if bool(state.estop) or bool(state.fault):
        return

    # ensure we can actually command motion; caller will still clamp by Mode
    from steuerung3d.core.mode import Mode
    if state.mode != Mode.LIVE:
        # leave plan armed; UI can ArmLiveMode or we can auto-arm elsewhere
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

    if all_done:
        stop_recover(state)
        state.rig_mode = RigMode.ARMED_SYNC
