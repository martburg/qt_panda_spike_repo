from __future__ import annotations

from .birds_eye_types import BirdsEyeAgeFacts, BirdsEyeMotionFacts, BirdsEyeSnapLike, BirdsEyeStateLike, LastIntentsMetaLike


def build_summary(
    *,
    mode_v: str,
    state: BirdsEyeStateLike,
    motion_facts: BirdsEyeMotionFacts,
    last_intents_meta: LastIntentsMetaLike,
) -> str:
    blocked_summary = ','.join(motion_facts.blocked_by)
    local_manual_summary = ','.join(motion_facts.local_manual_axes)
    selected_summary = ','.join(motion_facts.selected_lanes)
    moving_summary = ','.join(motion_facts.resolved_moving_targets)
    motion_allowed_i = int(bool(state.core_motion_allowed))
    return (
        f'core_mode={mode_v} motion_allowed={motion_allowed_i} blocked_by=[{blocked_summary}] '
        f'local_manual=[{local_manual_summary}] dm={int(motion_facts.joy_dm)} '
        f'sel=[{selected_summary}] moving=[{moving_summary}] '
        f'in=[{motion_facts.intents_types_str}] n={int(last_intents_meta.get("count", 0))} '
        f'reset_denied={int(motion_facts.reset_denied_total)}'
    )


def _age_ms(age: float | None) -> float | None:
    return None if age is None else age * 1000.0


def build_fields(
    *,
    snap: BirdsEyeSnapLike,
    state: BirdsEyeStateLike,
    mode_v: str,
    estop_v: bool,
    fault_v: bool,
    age_facts: BirdsEyeAgeFacts,
    motion_facts: BirdsEyeMotionFacts,
    last_intents_meta: LastIntentsMetaLike,
) -> dict[str, object]:
    cmd_frame = motion_facts.cmd_frame
    return {
        'component': 'core',
        'core_mode': str(mode_v),
        'blocked_by': list(motion_facts.blocked_payload),
        'joy_dm': bool(motion_facts.joy_dm),
        'joy_sel': bool(motion_facts.joy_sel),
        'deadman': bool(motion_facts.joy_dm),
        'selected_lanes': list(motion_facts.selected_lanes),
        'attached_lanes': list(motion_facts.attached_lanes),
        'resolved_moving_targets': list(motion_facts.resolved_moving_targets),
        'motion_allowed': bool(state.core_motion_allowed),
        'local_manual_axes': list(motion_facts.local_manual_axes),
        'local_manual_allowed': bool(motion_facts.local_manual_axes),
        'tick': int(snap.tick or 0),
        'mode': str(mode_v),
        'estop': estop_v,
        'fault': fault_v,
        'intents_in_count': int(last_intents_meta.get('count', 0)),
        'intents_in_types': motion_facts.intents_types_str,
        'cmd_estop_reset': bool(cmd_frame.estop_reset) if cmd_frame is not None else False,
        'cmd_resync': bool(cmd_frame.resync) if cmd_frame is not None else False,
        'axes': motion_facts.axes_snapshot,
        'reset_denied_total': int(motion_facts.reset_denied_total),
        'reset_denied_by_axis': dict(motion_facts.reset_denied_by_axis),
        'devices': motion_facts.devices[:32],
        'devices_n': len(motion_facts.devices),
        'age_int_ms': _age_ms(age_facts.age_int),
        'age_dev_ms': _age_ms(age_facts.age_dev),
        'age_cmd_ms': _age_ms(age_facts.age_cmd),
        'age_ui_ms': _age_ms(age_facts.age_ui),
        'age_c2_ms': _age_ms(age_facts.age_c2),
    }
