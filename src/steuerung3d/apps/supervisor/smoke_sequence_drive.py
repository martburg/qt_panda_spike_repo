from __future__ import annotations

import subprocess
from collections.abc import Iterable, Sequence
from pathlib import Path

from steuerung3d.apps.inputd_sim.control import InputdSimControl, UdpInputdSimControlOut
from steuerung3d.core.net import parse_hostport
from steuerung3d.core.stack_meta import ChildMeta
from steuerung3d.protocol.udp_channels import UdpIntentOut, close_udp_json_endpoint

from .actions_transport import UdpDensiActionOut
from .models import DensiRemoteAction, SupervisorProfile
from .smoke_sequence_bootstrap import (
    _raise_if_process_exited,
    _try_load_meta,
    bind_observer_telemetry_in,
)
from .smoke_sequence_extract import (
    extract_axis_device_ticks,
    extract_axis_estates,
    extract_axis_positions,
    extract_axis_system_time_tokens,
    extract_axis_velocities,
    system_time_tokens_advanced,
)
from .smoke_sequence_polling import PublishCadence, monotonic_deadline, poll_until_result
from .smoke_sequence_targets import (
    build_selected_estart_targets,
    build_selected_estop_reset_intents,
    build_selected_resync_intents,
)
from .smoke_sequence_types import (
    _ESTART_LOG_TOKEN,
    _RESET_LOG_TOKEN,
    ChkEsTasterObservation,
    MotionObservation,
    SmokeSequenceError,
    SystemTimeProgressObservation,
)


def drive_estop_reset_until_observed(
    *,
    session_dir: Path,
    process: subprocess.Popen[str],
    profile: SupervisorProfile,
    densi_process_names: Iterable[str],
    timeout_s: float,
    publish_interval_s: float,
    settle_s: float,
) -> tuple[set[str], int]:
    intents = build_selected_estop_reset_intents(profile)
    if not intents:
        raise SmokeSequenceError("no selected supervisor axes available for ESReset")

    pending = {str(name) for name in densi_process_names}
    observed: set[str] = set()
    publish_count = 0
    deadline = monotonic_deadline(timeout_s)

    intent_out = UdpIntentOut.connect(parse_hostport(profile.intent_out))
    cadence = PublishCadence(
        deadline=deadline,
        interval_s=float(publish_interval_s),
        settle_s=float(settle_s),
    )
    try:

        def _publish_intents() -> None:
            for intent in intents:
                intent_out.publish_intent(intent)

        def _observe() -> tuple[set[str], int] | None:
            nonlocal publish_count
            if cadence.maybe_publish(_publish_intents):
                publish_count += 1

            meta = _try_load_meta(session_dir)
            if meta is not None:
                for name in tuple(sorted(pending)):
                    child = meta.children.get(name)
                    if child is None:
                        continue
                    if _log_contains_token(child, _RESET_LOG_TOKEN):
                        pending.remove(name)
                        observed.add(name)
                if not pending:
                    return observed, publish_count
            return None

        result = poll_until_result(
            deadline=deadline,
            check_alive=lambda: _raise_if_process_exited(
                process, "supervisor exited while observing densi reset logs"
            ),
            observe=_observe,
        )
        if result is not None:
            return result
    finally:
        close_udp_json_endpoint(intent_out)

    missing = ", ".join(sorted(pending)) or "<none>"
    raise SmokeSequenceError(
        f"timed out waiting for densi reset log token {_RESET_LOG_TOKEN!r} in {missing} "
        f"after {publish_count} publish cycles"
    )


def drive_resync_until_system_time_observed(
    *,
    profile: SupervisorProfile,
    process: subprocess.Popen[str],
    axis_ids: Sequence[str],
    timeout_s: float,
    publish_interval_s: float,
    settle_s: float,
) -> tuple[SystemTimeProgressObservation, int]:
    if not axis_ids:
        raise SmokeSequenceError("no selected supervisor axes available for SystemTime observation")

    intents = build_selected_resync_intents(profile)
    if not intents:
        raise SmokeSequenceError("no selected supervisor axes available for Resync")

    observer_in, _observer_addr = bind_observer_telemetry_in(profile)
    intent_out = UdpIntentOut.connect(parse_hostport(profile.intent_out))
    deadline = monotonic_deadline(timeout_s)
    cadence = PublishCadence(
        deadline=deadline,
        interval_s=float(publish_interval_s),
        settle_s=float(settle_s),
    )
    publish_count = 0
    pending = {str(axis_id) for axis_id in axis_ids}
    first_by_axis: dict[str, str] = {}
    last_by_axis: dict[str, str] = {}
    first_tick_by_axis: dict[str, int] = {}
    last_tick_by_axis: dict[str, int] = {}
    try:

        def _publish_intents() -> None:
            for intent in intents:
                intent_out.publish_intent(intent)

        def _observe() -> tuple[SystemTimeProgressObservation, int] | None:
            nonlocal publish_count
            if cadence.maybe_publish(_publish_intents):
                publish_count += 1

            snaps = observer_in.drain_telemetry(limit=50)
            for snap in snaps:
                tokens = extract_axis_system_time_tokens(snap, axis_ids)
                ticks = extract_axis_device_ticks(snap, axis_ids)
                for axis_id, token in tokens.items():
                    if axis_id not in first_by_axis:
                        first_by_axis[axis_id] = token
                    last_by_axis[axis_id] = token
                for axis_id, tick in ticks.items():
                    if axis_id not in first_tick_by_axis:
                        first_tick_by_axis[axis_id] = tick
                    last_tick_by_axis[axis_id] = tick
                for axis_id in tuple(sorted(pending)):
                    first_tok = first_by_axis.get(axis_id, "")
                    last_tok = last_by_axis.get(axis_id, "")
                    if not first_tok or not last_tok:
                        continue
                    first_tick = int(first_tick_by_axis.get(axis_id, 0))
                    last_tick = int(last_tick_by_axis.get(axis_id, first_tick))
                    if system_time_tokens_advanced(first_tok, last_tok) or last_tick > first_tick:
                        pending.remove(axis_id)
                if not pending:
                    return (
                        SystemTimeProgressObservation(
                            observed_axis_ids=tuple(sorted(first_by_axis)),
                            first_by_axis=dict(first_by_axis),
                            last_by_axis=dict(last_by_axis),
                            first_tick_by_axis=dict(first_tick_by_axis),
                            last_tick_by_axis=dict(last_tick_by_axis),
                        ),
                        publish_count,
                    )
            return None

        result = poll_until_result(
            deadline=deadline,
            check_alive=lambda: _raise_if_process_exited(
                process, "supervisor exited while observing running SystemTime after Resync"
            ),
            observe=_observe,
        )
        if result is not None:
            return result
    finally:
        close_udp_json_endpoint(observer_in)
        close_udp_json_endpoint(intent_out)

    details = ", ".join(
        f"{axis_id}={first_by_axis.get(axis_id, '<none>')} -> {last_by_axis.get(axis_id, '<none>')} "
        f"[tick {first_tick_by_axis.get(axis_id, 0)} -> {last_tick_by_axis.get(axis_id, 0)}]"
        for axis_id in axis_ids
    )
    missing = ", ".join(sorted(pending)) or "<none>"
    raise SmokeSequenceError(
        "timed out waiting for running SystemTime tokens after Resync in "
        f"{missing}; last seen {details}; after {publish_count} resync publish cycles"
    )


def drive_chk_es_taster_until_ready(
    *,
    profile: SupervisorProfile,
    process: subprocess.Popen[str],
    axis_ids: Sequence[str],
    supervisor_action_in_addr: str,
    timeout_s: float,
    publish_interval_s: float,
    settle_s: float,
    brake_grace_s: float,
) -> tuple[ChkEsTasterObservation, int]:
    if not axis_ids:
        raise SmokeSequenceError("no selected supervisor axes available for chkEsTaster")

    if not str(supervisor_action_in_addr or "").strip():
        raise SmokeSequenceError("no supervisor smoke action input available for chkEsTaster")

    observer_in, _observer_addr = bind_observer_telemetry_in(profile)
    control_out = UdpDensiActionOut.connect(parse_hostport(supervisor_action_in_addr))

    axis_id_set = {str(axis_id) for axis_id in axis_ids}
    before_by_axis: dict[str, str] = {}
    first_active_by_axis: dict[str, str] = {}
    final_by_axis: dict[str, str] = {}
    armed_seen: set[str] = set()
    ready_seen: set[str] = set()
    publish_count = 0
    baseline_deadline = monotonic_deadline(min(1.0, max(0.25, float(timeout_s) * 0.25)))
    ready_deadline = monotonic_deadline(max(0.1, float(brake_grace_s) + 0.5))
    cadence = PublishCadence(
        deadline=ready_deadline,
        interval_s=float(publish_interval_s),
        settle_s=float(settle_s),
    )
    action = DensiRemoteAction("chk_es_taster", value=True)

    try:

        def _observe_baseline() -> bool | None:
            snaps = observer_in.drain_telemetry(limit=50)
            for snap in snaps:
                estates = extract_axis_estates(snap, axis_ids)
                for axis_id, estate in estates.items():
                    final_by_axis[axis_id] = estate
                    if axis_id not in before_by_axis and estate == "IDLE":
                        before_by_axis[axis_id] = estate
            if len(before_by_axis) >= len(axis_id_set):
                return True
            return None

        poll_until_result(
            deadline=baseline_deadline,
            check_alive=lambda: _raise_if_process_exited(
                process, "supervisor exited while observing pre-chkEsTaster idle state"
            ),
            observe=_observe_baseline,
        )

        def _observe_ready() -> tuple[ChkEsTasterObservation, int] | None:
            nonlocal publish_count
            if cadence.maybe_publish(lambda: control_out.publish_action(action)):
                publish_count += 1

            snaps = observer_in.drain_telemetry(limit=50)
            for snap in snaps:
                estates = extract_axis_estates(snap, axis_ids)
                for axis_id, estate in estates.items():
                    final_by_axis[axis_id] = estate
                    if axis_id not in before_by_axis:
                        before_by_axis[axis_id] = estate
                    if estate != "IDLE" and axis_id not in first_active_by_axis:
                        first_active_by_axis[axis_id] = estate
                    if estate == "ARMED":
                        armed_seen.add(axis_id)
                    if estate == "READY":
                        ready_seen.add(axis_id)
                pending = {
                    axis_id
                    for axis_id in axis_id_set
                    if not (axis_id in armed_seen and axis_id in ready_seen)
                }
                if not pending:
                    return (
                        ChkEsTasterObservation(
                            observed_axis_ids=tuple(sorted(axis_id_set)),
                            before_by_axis=dict(before_by_axis),
                            first_active_by_axis=dict(first_active_by_axis),
                            final_by_axis=dict(final_by_axis),
                            armed_axis_ids=tuple(sorted(armed_seen)),
                            ready_axis_ids=tuple(sorted(ready_seen)),
                        ),
                        publish_count,
                    )
            return None

        result = poll_until_result(
            deadline=ready_deadline,
            check_alive=lambda: _raise_if_process_exited(
                process, "supervisor exited while observing chkEsTaster phase progression"
            ),
            observe=_observe_ready,
        )
        if result is not None:
            return result
    finally:
        close_udp_json_endpoint(observer_in)
        close_udp_json_endpoint(control_out)

    missing = ", ".join(sorted(axis_id_set - (armed_seen & ready_seen))) or "<none>"
    details = ", ".join(
        f"{axis_id}=before:{before_by_axis.get(axis_id, '<none>')} first:{first_active_by_axis.get(axis_id, '<none>')} final:{final_by_axis.get(axis_id, '<none>')}"
        for axis_id in axis_ids
    )
    raise SmokeSequenceError(
        "timed out waiting for chkEsTaster phase progression IDLE->ARMED->READY in "
        f"{missing}; last seen {details}; after {publish_count} chk publish cycles"
    )


def drive_motion_until_stopped(
    *,
    profile: SupervisorProfile,
    process: subprocess.Popen[str],
    axis_ids: Sequence[str],
    inputd_sim_control_in_addr: str,
    timeout_s: float,
    publish_interval_s: float,
    pos_delta_min: float,
    vel_move_eps: float,
    vel_zero_eps: float,
    release_settle_s: float,
) -> tuple[MotionObservation, int]:
    if not axis_ids:
        raise SmokeSequenceError("no selected supervisor axes available for motion verification")
    if not str(inputd_sim_control_in_addr or "").strip():
        raise SmokeSequenceError(
            "inputd_sim control input is not configured; use the motion smoke stack/profile"
        )

    observer_in, _observer_addr = bind_observer_telemetry_in(profile)
    control_out = UdpInputdSimControlOut.connect(parse_hostport(inputd_sim_control_in_addr))

    axis_id_set = {str(axis_id) for axis_id in axis_ids}
    start_pos_by_axis: dict[str, float] = {}
    end_pos_by_axis: dict[str, float] = {}
    max_abs_vel_by_axis: dict[str, float] = {}
    final_abs_vel_by_axis: dict[str, float] = {}
    moving_axis_ids: set[str] = set()
    stopped_axis_ids: set[str] = set()
    stop_candidate_since: dict[str, float] = {}
    publish_count = 0
    baseline_deadline = monotonic_deadline(min(1.5, max(0.5, float(timeout_s) * 0.25)))
    start_command = InputdSimControl(action="start")
    motion_deadline = monotonic_deadline(max(0.5, float(timeout_s)))
    cadence = PublishCadence(deadline=motion_deadline, interval_s=float(publish_interval_s))

    try:

        def _observe_baseline() -> bool | None:
            for snap in observer_in.drain_telemetry(limit=50):
                positions = extract_axis_positions(snap, axis_ids)
                for axis_id, pos in positions.items():
                    start_pos_by_axis.setdefault(axis_id, float(pos))
                    end_pos_by_axis[axis_id] = float(pos)
            if len(start_pos_by_axis) >= len(axis_id_set):
                return True
            return None

        poll_until_result(
            deadline=baseline_deadline,
            check_alive=lambda: _raise_if_process_exited(
                process, "supervisor exited while observing pre-motion positions"
            ),
            observe=_observe_baseline,
        )
        if len(start_pos_by_axis) < len(axis_id_set):
            missing = ", ".join(sorted(axis_id_set - set(start_pos_by_axis))) or "<none>"
            raise SmokeSequenceError(f"timed out waiting for baseline positions in {missing}")

        def _observe_motion() -> tuple[MotionObservation, int] | None:
            nonlocal publish_count
            if not axis_id_set.issubset(moving_axis_ids):
                if cadence.maybe_publish(lambda: control_out.publish_command(start_command)):
                    publish_count += 1

            for snap in observer_in.drain_telemetry(limit=50):
                positions = extract_axis_positions(snap, axis_ids)
                velocities = extract_axis_velocities(snap, axis_ids)
                sample_time = monotonic_deadline(0.0, minimum_s=0.0)
                for axis_id, pos in positions.items():
                    end_pos_by_axis[axis_id] = float(pos)
                    start_pos = float(start_pos_by_axis.get(axis_id, pos))
                    delta = abs(float(pos) - start_pos)
                    if delta >= float(pos_delta_min):
                        moving_axis_ids.add(axis_id)
                for axis_id, vel in velocities.items():
                    abs_vel = abs(float(vel))
                    final_abs_vel_by_axis[axis_id] = abs_vel
                    max_abs_vel_by_axis[axis_id] = max(
                        abs_vel, float(max_abs_vel_by_axis.get(axis_id, 0.0))
                    )
                    if axis_id in moving_axis_ids and abs_vel <= float(vel_zero_eps):
                        stop_candidate_since.setdefault(axis_id, sample_time)
                        if sample_time - float(stop_candidate_since[axis_id]) >= float(
                            release_settle_s
                        ):
                            stopped_axis_ids.add(axis_id)
                    else:
                        stop_candidate_since.pop(axis_id, None)
                if axis_id_set.issubset(moving_axis_ids) and axis_id_set.issubset(stopped_axis_ids):
                    delta_by_axis = {
                        axis_id: float(end_pos_by_axis.get(axis_id, start_pos_by_axis[axis_id]))
                        - float(start_pos_by_axis[axis_id])
                        for axis_id in axis_ids
                        if axis_id in start_pos_by_axis
                    }
                    weak_motion = [
                        axis_id
                        for axis_id in axis_ids
                        if float(max_abs_vel_by_axis.get(axis_id, 0.0)) < float(vel_move_eps)
                    ]
                    if weak_motion:
                        details = ", ".join(
                            f"{axis_id} max_abs_vel={max_abs_vel_by_axis.get(axis_id, 0.0):.3f}"
                            for axis_id in weak_motion
                        )
                        raise SmokeSequenceError(
                            f"motion position changed but velocity stayed too small: {details}"
                        )
                    return (
                        MotionObservation(
                            moving_axis_ids=tuple(sorted(moving_axis_ids)),
                            stopped_axis_ids=tuple(sorted(stopped_axis_ids)),
                            start_pos_by_axis=dict(start_pos_by_axis),
                            end_pos_by_axis=dict(end_pos_by_axis),
                            delta_by_axis=dict(delta_by_axis),
                            max_abs_vel_by_axis=dict(max_abs_vel_by_axis),
                            final_abs_vel_by_axis=dict(final_abs_vel_by_axis),
                        ),
                        publish_count,
                    )
            return None

        result = poll_until_result(
            deadline=motion_deadline,
            check_alive=lambda: _raise_if_process_exited(
                process, "supervisor exited while observing motion after chkEsTaster"
            ),
            observe=_observe_motion,
        )
        if result is not None:
            return result
    finally:
        close_udp_json_endpoint(observer_in)
        close_udp_json_endpoint(control_out)

    delta_by_axis = {
        axis_id: float(end_pos_by_axis.get(axis_id, start_pos_by_axis.get(axis_id, 0.0)))
        - float(start_pos_by_axis.get(axis_id, 0.0))
        for axis_id in axis_ids
    }
    details = ", ".join(
        f"{axis_id}=start:{start_pos_by_axis.get(axis_id, 0.0):.3f} "
        f"end:{end_pos_by_axis.get(axis_id, start_pos_by_axis.get(axis_id, 0.0)):.3f} "
        f"delta:{delta_by_axis.get(axis_id, 0.0):.3f} "
        f"max_abs_vel:{max_abs_vel_by_axis.get(axis_id, 0.0):.3f} "
        f"final_abs_vel:{final_abs_vel_by_axis.get(axis_id, 0.0):.3f}"
        for axis_id in axis_ids
    )
    raise SmokeSequenceError(
        "timed out waiting for motion and stop after inputd_sim start; "
        f"last seen {details}; after {publish_count} motion start commands"
    )


def drive_estart_until_observed(
    *,
    session_dir: Path,
    process: subprocess.Popen[str],
    profile: SupervisorProfile,
    timeout_s: float,
    publish_interval_s: float,
    settle_s: float,
) -> tuple[set[str], int]:
    targets = build_selected_estart_targets(profile)
    if not targets:
        raise SmokeSequenceError(
            "no selected supervisor axes with densi_action_out available for ESStart"
        )

    pending = {target.densi_process_name for target in targets}
    observed: set[str] = set()
    publish_count = 0
    deadline = monotonic_deadline(timeout_s)

    tx_by_name = {
        target.densi_process_name: UdpDensiActionOut.connect(parse_hostport(target.action_out_addr))
        for target in targets
    }
    action = DensiRemoteAction("estart")
    cadence = PublishCadence(
        deadline=deadline,
        interval_s=float(publish_interval_s),
        settle_s=float(settle_s),
    )
    try:

        def _publish_estart() -> None:
            for tx in tx_by_name.values():
                tx.publish_action(action)

        def _observe() -> tuple[set[str], int] | None:
            nonlocal publish_count
            if cadence.maybe_publish(_publish_estart):
                publish_count += 1

            meta = _try_load_meta(session_dir)
            if meta is not None:
                for name in tuple(sorted(pending)):
                    child = meta.children.get(name)
                    if child is None:
                        continue
                    if _log_contains_token(child, _ESTART_LOG_TOKEN):
                        pending.remove(name)
                        observed.add(name)
                if not pending:
                    return observed, publish_count
            return None

        result = poll_until_result(
            deadline=deadline,
            check_alive=lambda: _raise_if_process_exited(
                process, "supervisor exited while observing densi ESStart logs"
            ),
            observe=_observe,
        )
        if result is not None:
            return result
    finally:
        for tx in tx_by_name.values():
            close_udp_json_endpoint(tx)

    missing = ", ".join(sorted(pending)) or "<none>"
    raise SmokeSequenceError(
        f"timed out waiting for densi ESStart log token {_ESTART_LOG_TOKEN!r} in {missing} "
        f"after {publish_count} publish cycles"
    )


def wait_for_core_log_token(
    *,
    session_dir: Path,
    process: subprocess.Popen[str],
    token: str,
    timeout_s: float,
) -> None:
    deadline = monotonic_deadline(timeout_s)

    def _observe() -> bool | None:
        meta = _try_load_meta(session_dir)
        if meta is None:
            return None
        child = meta.children.get("core")
        if child is not None and _log_contains_token(child, token):
            return True
        return None

    result = poll_until_result(
        deadline=deadline,
        check_alive=lambda: _raise_if_process_exited(
            process, "supervisor exited while waiting for core readiness"
        ),
        observe=_observe,
    )
    if result is not None:
        return
    raise SmokeSequenceError(f"timed out waiting for core log token {token!r}")


def _log_contains_token(child: ChildMeta, token: str) -> bool:
    log_path = Path(str(child.log_path))
    if not log_path.exists():
        return False
    try:
        text = log_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    return token in text
