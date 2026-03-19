from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Final, cast

from steuerung3d.apps.hi_p.smoke_control import HiPSmokeCommand, UdpHiPSmokeControlOut
from steuerung3d.apps.hi_p.smoke_param_specs import SAFE_HIP_SMOKE_PARAMS, HiPSmokeParamSpec
from steuerung3d.apps.inputd_sim.config import load_inputd_sim_config
from steuerung3d.apps.inputd_sim.control import InputdSimControl, UdpInputdSimControlOut
from steuerung3d.core.intents import RequestEstopReset, RequestResync
from steuerung3d.core.net import parse_hostport
from steuerung3d.core.process_liveness import pid_is_alive
from steuerung3d.core.stack_loader import load_stack_profile
from steuerung3d.core.stack_meta import ChildMeta, StackMeta, find_latest_session_dir, load_meta
from steuerung3d.core.stack_spec import StackSpec
from steuerung3d.protocol.udp_channels import UdpIntentOut, UdpTelemetryIn, close_udp_json_endpoint

from .actions_transport import UdpDensiActionOut
from .models import DensiRemoteAction, SupervisorProfile
from .profile_loader import load_profile
from .row_estate import estate_from_word

_RESET_LOG_TOKEN: Final[str] = "cmd_estop_reset=True"
_ESTART_LOG_TOKEN: Final[str] = "ESStart pressed"
_CORE_IDLE_TOKEN: Final[str] = "core_mode=IDLE"
_HIP_SMOKE_CONTROL_BASE: Final[int] = 54001


def _as_str_object_mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        return {}
    return cast(Mapping[str, object], value)


def _mapping_attr(obj: object, name: str) -> Mapping[str, object]:
    return _as_str_object_mapping(getattr(obj, name, None))


def _mapping_value(mapping: Mapping[str, object], key: str) -> object | None:
    return mapping.get(key)


def _text_attr(obj: object, name: str) -> str:
    return str(getattr(obj, name, "") or "")


def _coerce_float(value: object) -> float | None:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except Exception:
            return None
    return None


def _coerce_int(value: object) -> int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except Exception:
            return None
    return None


def _float_attr(obj: object, name: str, default: float = 0.0) -> float:
    raw = getattr(obj, name, default)
    value = _coerce_float(raw)
    if value is None:
        return float(default)
    return value


def _int_attr(obj: object, name: str, default: int = 0) -> int:
    raw = getattr(obj, name, default)
    value = _coerce_int(raw)
    if value is None:
        return int(default)
    return value


@dataclass(frozen=True)
class SmokeSequenceConfig:
    supervisor_profile_path: Path
    startup_timeout_s: float = 20.0
    ready_grace_s: float = 1.0
    observe_timeout_s: float = 8.0
    settle_s: float = 0.25
    publish_interval_s: float = 0.25
    keep_running: bool = False
    brake_grace_s: float = 2.0
    motion_pos_delta_min: float = 0.2
    motion_vel_move_eps: float = 0.05
    motion_vel_zero_eps: float = 0.05
    motion_release_settle_s: float = 0.5
    hip_param_axis_id: str = ""
    hip_param_restore_after_write: bool = True


@dataclass(frozen=True)
class SmokeSequenceResult:
    session_dir: Path
    selected_axis_ids: tuple[str, ...]
    observed_reset_log_names: tuple[str, ...]
    observed_estart_log_names: tuple[str, ...] = ()
    observed_system_time_axis_ids: tuple[str, ...] = ()
    system_time_first_by_axis: Mapping[str, str] | None = None
    system_time_last_by_axis: Mapping[str, str] | None = None
    system_time_first_tick_by_axis: Mapping[str, int] | None = None
    system_time_last_tick_by_axis: Mapping[str, int] | None = None
    reset_publish_count: int = 0
    estart_publish_count: int = 0
    resync_publish_count: int = 0
    chk_taster_publish_count: int = 0
    observed_chk_ready_axis_ids: tuple[str, ...] = ()
    chk_phase_before_by_axis: Mapping[str, str] | None = None
    chk_phase_first_active_by_axis: Mapping[str, str] | None = None
    chk_phase_final_by_axis: Mapping[str, str] | None = None
    chk_armed_axis_ids: tuple[str, ...] = ()
    chk_ready_axis_ids: tuple[str, ...] = ()
    motion_command_publish_count: int = 0
    observed_motion_axis_ids: tuple[str, ...] = ()
    observed_stop_axis_ids: tuple[str, ...] = ()
    motion_start_pos_by_axis: Mapping[str, float] | None = None
    motion_end_pos_by_axis: Mapping[str, float] | None = None
    motion_delta_by_axis: Mapping[str, float] | None = None
    motion_max_abs_vel_by_axis: Mapping[str, float] | None = None
    motion_final_abs_vel_by_axis: Mapping[str, float] | None = None


class SmokeSequenceError(RuntimeError):
    pass


@dataclass(frozen=True)
class HiPParamSmokeResult:
    session_dir: Path
    axis_id: str
    hip_id: str
    observed_reset_log_names: tuple[str, ...]
    observed_estart_log_names: tuple[str, ...]
    observed_system_time_axis_ids: tuple[str, ...]
    reset_publish_count: int
    estart_publish_count: int
    resync_publish_count: int
    open_hip_command_count: int
    param_command_count: int
    param_restore_command_count: int
    selected_axis_ids: tuple[str, ...] = ()
    owner_before: str = ""
    owner_after_open: str = ""
    parameter_name: str = ""
    parameter_group: str = ""
    original_value: float = 0.0
    edited_value: float = 0.0
    observed_value_after_write: float = 0.0
    observed_commit_status_after_write: str = ""
    observed_value_after_restore: float = 0.0
    observed_commit_status_after_restore: str = ""
    restored: bool = False


@dataclass(frozen=True)
class HiPOpenObservation:
    axis_id: str
    owner_before: str
    owner_after: str


@dataclass(frozen=True)
class HiPParamObservation:
    observed_value: float
    commit_status: str


@dataclass(frozen=True)
class SystemTimeProgressObservation:
    observed_axis_ids: tuple[str, ...]
    first_by_axis: Mapping[str, str]
    last_by_axis: Mapping[str, str]
    first_tick_by_axis: Mapping[str, int]
    last_tick_by_axis: Mapping[str, int]


@dataclass(frozen=True)
class ChkEsTasterObservation:
    observed_axis_ids: tuple[str, ...]
    before_by_axis: Mapping[str, str]
    first_active_by_axis: Mapping[str, str]
    final_by_axis: Mapping[str, str]
    armed_axis_ids: tuple[str, ...]
    ready_axis_ids: tuple[str, ...]


@dataclass(frozen=True)
class MotionObservation:
    moving_axis_ids: tuple[str, ...]
    stopped_axis_ids: tuple[str, ...]
    start_pos_by_axis: Mapping[str, float]
    end_pos_by_axis: Mapping[str, float]
    delta_by_axis: Mapping[str, float]
    max_abs_vel_by_axis: Mapping[str, float]
    final_abs_vel_by_axis: Mapping[str, float]


@dataclass(frozen=True)
class _IdleSyncedBootstrap:
    launched: _LaunchedSupervisor
    selected_axis_ids: tuple[str, ...]
    observed_reset: set[str]
    observed_estart: set[str]
    system_time_progress: SystemTimeProgressObservation
    reset_publish_count: int
    estart_publish_count: int
    resync_publish_count: int


@dataclass
class _LaunchedSupervisor:
    process: subprocess.Popen[str]
    session_dir: Path
    profile: SupervisorProfile
    stack_profile_path: Path
    supervisor_action_in_addr: str
    inputd_sim_control_in_addr: str
    hip_smoke_control_base: int


@dataclass(frozen=True)
class _SelectedActionTarget:
    axis_id: str
    unit_id: str
    densi_process_name: str
    action_out_addr: str


def build_selected_estop_reset_intents(profile: SupervisorProfile) -> tuple[RequestEstopReset, ...]:
    intents: list[RequestEstopReset] = []
    for axis in profile.axes:
        if not bool(axis.selected):
            continue
        intents.append(
            RequestEstopReset(
                axis_id=str(axis.axis_id),
                hip_id=str(profile.supervisor_id),
                actor_kind="supervisor",
            )
        )
    return tuple(intents)


def build_selected_resync_intents(profile: SupervisorProfile) -> tuple[RequestResync, ...]:
    intents: list[RequestResync] = []
    for axis in profile.axes:
        if not bool(axis.selected):
            continue
        intents.append(
            RequestResync(
                axis_id=str(axis.axis_id),
                hip_id=str(profile.supervisor_id),
                actor_kind="supervisor",
            )
        )
    return tuple(intents)


def build_selected_estart_targets(profile: SupervisorProfile) -> tuple[_SelectedActionTarget, ...]:
    targets: list[_SelectedActionTarget] = []
    for axis in profile.axes:
        if not bool(axis.selected):
            continue
        addr = str(axis.densi_action_out or "").strip()
        if not addr:
            continue
        targets.append(
            _SelectedActionTarget(
                axis_id=str(axis.axis_id),
                unit_id=str(axis.unit_id),
                densi_process_name=f"densi-{axis.axis_id}",
                action_out_addr=addr,
            )
        )
    return tuple(targets)


def densi_process_names_for_axes(axis_ids: Sequence[str]) -> tuple[str, ...]:
    return tuple(f"densi-{axis_id}" for axis_id in axis_ids)


def infer_observer_telemetry_candidates(profile: SupervisorProfile) -> tuple[tuple[str, int], ...]:
    host, port = parse_hostport(profile.telem_in)
    highest_offset = max(1, len(tuple(profile.axes or ())))
    return tuple((host, int(port) + offset) for offset in range(1, highest_offset + 1))


def infer_hip_observer_telemetry_candidates(
    profile: SupervisorProfile,
) -> tuple[tuple[str, int], ...]:
    host, port = parse_hostport(profile.telem_in)
    reserved_offsets = 1 + len(tuple(profile.axes or ()))
    return ((host, int(port) + reserved_offsets + 1),)


def parse_system_time_token(token: str) -> datetime | None:
    raw = str(token or "").strip()
    if not raw or not raw.endswith(" ms"):
        return None
    stem = raw[:-3].rstrip()
    try:
        dt_part, ms_part = stem.rsplit(" ", 1)
        return datetime.strptime(f"{dt_part}.{int(ms_part):03d}", "%d-%m-%Y %H:%M:%S.%f")
    except Exception:
        return None


def system_time_tokens_advanced(previous: str, current: str) -> bool:
    prev_raw = str(previous or "").strip()
    curr_raw = str(current or "").strip()
    if not prev_raw or not curr_raw:
        return False
    prev_dt = parse_system_time_token(prev_raw)
    curr_dt = parse_system_time_token(curr_raw)
    if prev_dt is not None and curr_dt is not None:
        return curr_dt > prev_dt
    return curr_raw != prev_raw


def extract_axis_system_time_tokens(snap: object, axis_ids: Sequence[str]) -> dict[str, str]:
    tail_by_axis = _mapping_attr(snap, "axis_plc_uplink_tail")
    tokens: dict[str, str] = {}
    for axis_id in axis_ids:
        axis_tail = _as_str_object_mapping(_mapping_value(tail_by_axis, axis_id))
        token = str(_mapping_value(axis_tail, "SystemTime") or "").strip()
        if token:
            tokens[str(axis_id)] = token
    return tokens


def extract_axis_device_ticks(snap: object, axis_ids: Sequence[str]) -> dict[str, int]:
    axes = _mapping_attr(snap, "axes")
    ticks: dict[str, int] = {}
    for axis_id in axis_ids:
        axis_telem = _mapping_value(axes, axis_id)
        if axis_telem is None:
            continue
        ticks[str(axis_id)] = _int_attr(axis_telem, "device_tick", 0)
    return ticks


def extract_axis_estates(snap: object, axis_ids: Sequence[str]) -> dict[str, str]:
    word_by_axis = _mapping_attr(snap, "axis_estop_status_word")
    estates: dict[str, str] = {}
    for axis_id in axis_ids:
        raw_word = _mapping_value(word_by_axis, axis_id)
        if raw_word is None:
            continue
        word = _coerce_int(raw_word)
        if word is None:
            continue
        try:
            estates[str(axis_id)] = str(estate_from_word(word)).upper()
        except Exception:
            continue
    return estates


def extract_axis_positions(snap: object, axis_ids: Sequence[str]) -> dict[str, float]:
    axes = _mapping_attr(snap, "axes")
    positions: dict[str, float] = {}
    for axis_id in axis_ids:
        axis_telem = _mapping_value(axes, axis_id)
        if axis_telem is None:
            continue
        positions[str(axis_id)] = _float_attr(axis_telem, "pos", 0.0)
    return positions


def extract_axis_velocities(snap: object, axis_ids: Sequence[str]) -> dict[str, float]:
    axes = _mapping_attr(snap, "axes")
    velocities: dict[str, float] = {}
    for axis_id in axis_ids:
        axis_telem = _mapping_value(axes, axis_id)
        if axis_telem is None:
            continue
        velocities[str(axis_id)] = _float_attr(axis_telem, "vel", 0.0)
    return velocities


def extract_axis_owner(snap: object, axis_id: str) -> str:
    densis = _mapping_attr(snap, "densis")
    densi = _mapping_value(densis, axis_id)
    if densi is None:
        return ""
    densi_map = _as_str_object_mapping(densi)
    if densi_map:
        claimed = str(_mapping_value(densi_map, "claimed_by_hip") or "").strip()
        owner = str(_mapping_value(densi_map, "owner") or "").strip()
        return claimed or owner
    return _text_attr(densi, "claimed_by_hip") or _text_attr(densi, "owner")


def extract_axis_param_value(snap: object, axis_id: str, name: str) -> float | None:
    axis_params = _mapping_attr(snap, "axis_params")
    params = _mapping_value(axis_params, axis_id)
    if params is not None:
        params_map = _as_str_object_mapping(params)
        if params_map:
            raw = _mapping_value(params_map, name)
        else:
            raw = getattr(params, name, None)
        if raw is not None:
            value = _coerce_float(raw)
            if value is not None:
                return value

    params_top = _mapping_attr(snap, "params")
    raw_top = _mapping_value(params_top, name)
    if raw_top is None:
        return None
    return _coerce_float(raw_top)


def extract_axis_param_commit_status(snap: object, axis_id: str) -> str:
    statuses = _mapping_attr(snap, "axis_param_commit_status")
    raw = _mapping_value(statuses, axis_id)
    raw_map = _as_str_object_mapping(raw)
    if raw_map:
        status = str(_mapping_value(raw_map, "status") or _mapping_value(raw_map, "state") or "")
        if status:
            return status
    elif raw is not None:
        status = str(raw or "")
        if status:
            return status

    return _text_attr(snap, "param_commit_status")


def _axis_config_by_axis_id(profile: SupervisorProfile, axis_id: str) -> object | None:
    for axis in profile.axes:
        if str(axis.axis_id) == str(axis_id):
            return axis
    return None


def infer_hip_smoke_control_addr(profile: SupervisorProfile, axis_id: str, *, base: int) -> str:
    for idx, axis in enumerate(profile.axes):
        if str(axis.axis_id) == str(axis_id):
            return f"127.0.0.1:{int(base) + idx}"
    return ""


def _select_safe_hip_param_spec(name: str = "") -> HiPSmokeParamSpec:
    requested = str(name or "").strip()
    if requested:
        for spec in SAFE_HIP_SMOKE_PARAMS:
            if str(spec.name) == requested:
                return spec
        raise SmokeSequenceError(f"unknown safe HiP smoke parameter {requested!r}")
    if not SAFE_HIP_SMOKE_PARAMS:
        raise SmokeSequenceError("no safe HiP smoke parameters configured")
    return SAFE_HIP_SMOKE_PARAMS[0]


def _hostport_to_str(addr: tuple[str, int] | None) -> str:
    if addr is None:
        return ""
    host, port = addr
    return f"{host}:{int(port)}"


def _resolve_service_config_path(raw_path: str, *, cwd: Path) -> Path:
    path = Path(raw_path)
    return path if path.is_absolute() else (cwd / path).resolve()


def _resolve_inputd_sim_control_in_addr(stack_spec: StackSpec, *, cwd: Path) -> str:
    service = stack_spec.services.get("inputd_sim")
    if service is None or not bool(service.enabled) or not str(service.config or "").strip():
        return ""
    cfg = load_inputd_sim_config(_resolve_service_config_path(str(service.config), cwd=cwd))
    return _hostport_to_str(cfg.control_in_addr)


def _bootstrap_to_idle_synced(config: SmokeSequenceConfig) -> _IdleSyncedBootstrap:
    launched = _launch_supervisor(config)
    try:
        if config.ready_grace_s > 0.0:
            time.sleep(float(config.ready_grace_s))
        selected_axis_ids = tuple(
            intent.axis_id for intent in build_selected_estop_reset_intents(launched.profile)
        )
        densi_names = densi_process_names_for_axes(selected_axis_ids)
        observed_reset, reset_publish_count = _drive_estop_reset_until_observed(
            session_dir=launched.session_dir,
            process=launched.process,
            profile=launched.profile,
            densi_process_names=densi_names,
            timeout_s=float(config.observe_timeout_s),
            publish_interval_s=float(config.publish_interval_s),
            settle_s=float(config.settle_s),
        )
        _wait_for_core_log_token(
            session_dir=launched.session_dir,
            process=launched.process,
            token=_CORE_IDLE_TOKEN,
            timeout_s=min(max(1.0, float(config.observe_timeout_s)), 5.0),
        )
        observed_estart, estart_publish_count = _drive_estart_until_observed(
            session_dir=launched.session_dir,
            process=launched.process,
            profile=launched.profile,
            timeout_s=float(config.observe_timeout_s),
            publish_interval_s=float(config.publish_interval_s),
            settle_s=float(config.settle_s),
        )
        system_time_progress, resync_publish_count = _drive_resync_until_system_time_observed(
            profile=launched.profile,
            process=launched.process,
            axis_ids=selected_axis_ids,
            timeout_s=float(config.observe_timeout_s),
            publish_interval_s=float(config.publish_interval_s),
            settle_s=float(config.settle_s),
        )
        return _IdleSyncedBootstrap(
            launched=launched,
            selected_axis_ids=selected_axis_ids,
            observed_reset=observed_reset,
            observed_estart=observed_estart,
            system_time_progress=system_time_progress,
            reset_publish_count=reset_publish_count,
            estart_publish_count=estart_publish_count,
            resync_publish_count=resync_publish_count,
        )
    except Exception:
        if not config.keep_running:
            _shutdown_supervisor_stack(launched)
        raise


def run_hip_param_sequence(config: SmokeSequenceConfig) -> HiPParamSmokeResult:
    boot = _bootstrap_to_idle_synced(config)
    launched = boot.launched
    axis_id = str(
        config.hip_param_axis_id or (boot.selected_axis_ids[0] if boot.selected_axis_ids else "")
    )
    if not axis_id:
        raise SmokeSequenceError("no axis available for HiP parameter smoke scenario")
    axis_cfg = _axis_config_by_axis_id(launched.profile, axis_id)
    if axis_cfg is None:
        raise SmokeSequenceError(f"axis {axis_id!r} not found in supervisor profile")
    hip_id = str(getattr(axis_cfg, "hip_id", "") or "")
    if not hip_id:
        raise SmokeSequenceError(f"axis {axis_id!r} has no hip_id configured")
    spec = _select_safe_hip_param_spec()
    try:
        open_obs, open_count = _drive_open_hip_until_owned(
            profile=launched.profile,
            process=launched.process,
            session_dir=launched.session_dir,
            axis_id=axis_id,
            supervisor_action_in_addr=launched.supervisor_action_in_addr,
            hip_id=hip_id,
            hip_smoke_control_base=int(launched.hip_smoke_control_base),
            timeout_s=float(config.observe_timeout_s),
        )
        baseline_from_observer = True
        try:
            original_value = _read_axis_param_baseline(
                profile=launched.profile,
                process=launched.process,
                axis_id=axis_id,
                param_name=spec.name,
                timeout_s=float(config.observe_timeout_s),
            )
        except SmokeSequenceError:
            baseline_from_observer = False
            if spec.restore_value is None:
                raise
            original_value = float(spec.restore_value)
        write_obs, param_cmd_count = _drive_hip_param_command_until_observed(
            axis_id=axis_id,
            param_name=spec.name,
            group=spec.group,
            desired_value=float(spec.test_value),
            hip_control_addr=infer_hip_smoke_control_addr(
                launched.profile, axis_id, base=int(launched.hip_smoke_control_base)
            ),
            session_dir=launched.session_dir,
            profile=launched.profile,
            process=launched.process,
            timeout_s=float(config.observe_timeout_s),
        )
        restored = bool(
            config.hip_param_restore_after_write
            and (baseline_from_observer or spec.restore_value is not None)
        )
        restore_obs = HiPParamObservation(
            observed_value=write_obs.observed_value, commit_status=write_obs.commit_status
        )
        restore_count = 0
        if restored:
            restore_obs, restore_count = _drive_hip_param_command_until_observed(
                axis_id=axis_id,
                param_name=spec.name,
                group=spec.group,
                desired_value=float(original_value),
                hip_control_addr=infer_hip_smoke_control_addr(
                    launched.profile, axis_id, base=int(launched.hip_smoke_control_base)
                ),
                session_dir=launched.session_dir,
                profile=launched.profile,
                process=launched.process,
                timeout_s=float(config.observe_timeout_s),
            )
        return HiPParamSmokeResult(
            session_dir=launched.session_dir,
            axis_id=axis_id,
            hip_id=hip_id,
            observed_reset_log_names=tuple(sorted(boot.observed_reset)),
            observed_estart_log_names=tuple(sorted(boot.observed_estart)),
            observed_system_time_axis_ids=tuple(
                sorted(boot.system_time_progress.observed_axis_ids)
            ),
            reset_publish_count=boot.reset_publish_count,
            estart_publish_count=boot.estart_publish_count,
            resync_publish_count=boot.resync_publish_count,
            open_hip_command_count=open_count,
            param_command_count=param_cmd_count,
            param_restore_command_count=restore_count,
            selected_axis_ids=boot.selected_axis_ids,
            owner_before=open_obs.owner_before,
            owner_after_open=open_obs.owner_after,
            parameter_name=spec.name,
            parameter_group=spec.group,
            original_value=float(original_value),
            edited_value=float(spec.test_value),
            observed_value_after_write=float(write_obs.observed_value),
            observed_commit_status_after_write=str(write_obs.commit_status),
            observed_value_after_restore=float(restore_obs.observed_value),
            observed_commit_status_after_restore=str(restore_obs.commit_status),
            restored=restored,
        )
    finally:
        if not config.keep_running:
            _shutdown_supervisor_stack(launched)


def run_esreset_estart_resync_sequence(config: SmokeSequenceConfig) -> SmokeSequenceResult:
    boot = _bootstrap_to_idle_synced(config)
    launched = boot.launched
    try:
        selected_axis_ids = boot.selected_axis_ids
        observed_reset = boot.observed_reset
        reset_publish_count = boot.reset_publish_count
        observed_estart = boot.observed_estart
        estart_publish_count = boot.estart_publish_count
        system_time_progress = boot.system_time_progress
        resync_publish_count = boot.resync_publish_count
        chk_taster_progress, chk_taster_publish_count = _drive_chk_es_taster_until_ready(
            profile=launched.profile,
            process=launched.process,
            axis_ids=selected_axis_ids,
            supervisor_action_in_addr=launched.supervisor_action_in_addr,
            timeout_s=float(config.observe_timeout_s),
            publish_interval_s=float(config.publish_interval_s),
            settle_s=float(config.settle_s),
            brake_grace_s=float(config.brake_grace_s),
        )
        motion_progress, motion_command_publish_count = _drive_motion_until_stopped(
            profile=launched.profile,
            process=launched.process,
            axis_ids=selected_axis_ids,
            inputd_sim_control_in_addr=launched.inputd_sim_control_in_addr,
            timeout_s=float(config.observe_timeout_s),
            publish_interval_s=float(config.publish_interval_s),
            pos_delta_min=float(config.motion_pos_delta_min),
            vel_move_eps=float(config.motion_vel_move_eps),
            vel_zero_eps=float(config.motion_vel_zero_eps),
            release_settle_s=float(config.motion_release_settle_s),
        )
        return SmokeSequenceResult(
            session_dir=launched.session_dir,
            selected_axis_ids=selected_axis_ids,
            observed_reset_log_names=tuple(sorted(observed_reset)),
            observed_estart_log_names=tuple(sorted(observed_estart)),
            observed_system_time_axis_ids=tuple(sorted(system_time_progress.observed_axis_ids)),
            system_time_first_by_axis=dict(system_time_progress.first_by_axis),
            system_time_last_by_axis=dict(system_time_progress.last_by_axis),
            system_time_first_tick_by_axis=dict(system_time_progress.first_tick_by_axis),
            system_time_last_tick_by_axis=dict(system_time_progress.last_tick_by_axis),
            reset_publish_count=reset_publish_count,
            estart_publish_count=estart_publish_count,
            resync_publish_count=resync_publish_count,
            chk_taster_publish_count=chk_taster_publish_count,
            observed_chk_ready_axis_ids=tuple(sorted(chk_taster_progress.observed_axis_ids)),
            chk_phase_before_by_axis=dict(chk_taster_progress.before_by_axis),
            chk_phase_first_active_by_axis=dict(chk_taster_progress.first_active_by_axis),
            chk_phase_final_by_axis=dict(chk_taster_progress.final_by_axis),
            chk_armed_axis_ids=tuple(sorted(chk_taster_progress.armed_axis_ids)),
            chk_ready_axis_ids=tuple(sorted(chk_taster_progress.ready_axis_ids)),
            motion_command_publish_count=motion_command_publish_count,
            observed_motion_axis_ids=tuple(sorted(motion_progress.moving_axis_ids)),
            observed_stop_axis_ids=tuple(sorted(motion_progress.stopped_axis_ids)),
            motion_start_pos_by_axis=dict(motion_progress.start_pos_by_axis),
            motion_end_pos_by_axis=dict(motion_progress.end_pos_by_axis),
            motion_delta_by_axis=dict(motion_progress.delta_by_axis),
            motion_max_abs_vel_by_axis=dict(motion_progress.max_abs_vel_by_axis),
            motion_final_abs_vel_by_axis=dict(motion_progress.final_abs_vel_by_axis),
        )
    finally:
        if not config.keep_running:
            _shutdown_supervisor_stack(launched)


def _launch_supervisor(config: SmokeSequenceConfig) -> _LaunchedSupervisor:
    supervisor_profile_path = Path(config.supervisor_profile_path)
    profile = load_profile(supervisor_profile_path)
    stack_profile_path = Path(profile.launch_stack)
    stack_spec = load_stack_profile(stack_profile_path)
    stack_base = Path(".run") / str(stack_spec.name)
    previous_session = find_latest_session_dir(stack_base)

    supervisor_action_in_addr = _reserve_loopback_udp_addr()
    inputd_sim_control_in_addr = _resolve_inputd_sim_control_in_addr(stack_spec, cwd=Path.cwd())
    env = os.environ.copy()
    env["STEUERUNG3D_SUPERVISOR_ACTION_IN"] = supervisor_action_in_addr
    env["STEUERUNG3D_SUPERVISOR_HIP_SMOKE_BASE"] = str(_HIP_SMOKE_CONTROL_BASE)

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "steuerung3d",
            "sup",
            "--profile",
            os.fspath(supervisor_profile_path),
        ],
        cwd=Path.cwd(),
        text=True,
        env=env,
    )

    session_dir = _wait_for_new_session(
        stack_base=stack_base,
        previous_session=previous_session,
        process=proc,
        timeout_s=float(config.startup_timeout_s),
    )
    required_names = _required_process_names(profile, stack_spec=stack_spec)
    _wait_for_live_children(
        session_dir=session_dir,
        process=proc,
        required_names=required_names,
        timeout_s=float(config.startup_timeout_s),
    )
    return _LaunchedSupervisor(
        process=proc,
        session_dir=session_dir,
        profile=profile,
        stack_profile_path=stack_profile_path,
        supervisor_action_in_addr=supervisor_action_in_addr,
        inputd_sim_control_in_addr=inputd_sim_control_in_addr,
        hip_smoke_control_base=int(_HIP_SMOKE_CONTROL_BASE),
    )


def _reserve_loopback_udp_addr() -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(("127.0.0.1", 0))
        host, port = sock.getsockname()[:2]
    return f"{host}:{int(port)}"


def _required_process_names(profile: SupervisorProfile, *, stack_spec: StackSpec) -> set[str]:
    names = {"core"}
    for axis in profile.axes:
        names.add(f"densi-{axis.axis_id}")
    for service_name in ("joy2intent", "inputd", "inputd_sim"):
        service = stack_spec.services.get(service_name)
        if service is not None and bool(service.enabled) and service.mode == "single":
            names.add(service_name)
    return names


def _wait_for_new_session(
    *,
    stack_base: Path,
    previous_session: Path | None,
    process: subprocess.Popen[str],
    timeout_s: float,
) -> Path:
    deadline = time.monotonic() + max(0.1, float(timeout_s))
    while time.monotonic() < deadline:
        _raise_if_process_exited(process, "supervisor exited before stack session appeared")
        current = find_latest_session_dir(stack_base)
        if current is not None and current != previous_session:
            return current
        time.sleep(0.10)
    raise SmokeSequenceError(f"timed out waiting for new stack session under {stack_base}")


def _wait_for_live_children(
    *,
    session_dir: Path,
    process: subprocess.Popen[str],
    required_names: set[str],
    timeout_s: float,
) -> StackMeta:
    deadline = time.monotonic() + max(0.1, float(timeout_s))
    last_alive: set[str] = set()
    while time.monotonic() < deadline:
        _raise_if_process_exited(process, "supervisor exited while waiting for child services")
        meta = _try_load_meta(session_dir)
        if meta is None:
            time.sleep(0.10)
            continue
        alive = {
            name
            for name, child in meta.children.items()
            if pid_is_alive(int(getattr(child, "pid", 0) or 0))
        }
        last_alive = alive
        if required_names.issubset(alive):
            return meta
        time.sleep(0.10)
    missing = sorted(required_names - last_alive)
    raise SmokeSequenceError(
        f"timed out waiting for child services {missing} in session {session_dir}"
    )


def _drive_estop_reset_until_observed(
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
    deadline = time.monotonic() + max(0.1, float(timeout_s))
    next_publish_at = time.monotonic()
    publish_every_s = max(0.05, float(publish_interval_s))
    settle = max(0.0, float(settle_s))

    intent_out = UdpIntentOut.connect(parse_hostport(profile.intent_out))
    try:
        while time.monotonic() < deadline:
            _raise_if_process_exited(process, "supervisor exited while observing densi reset logs")
            now = time.monotonic()
            if now >= next_publish_at:
                for intent in intents:
                    intent_out.publish_intent(intent)
                publish_count += 1
                next_publish_at = now + publish_every_s
                if settle > 0.0:
                    time.sleep(min(settle, max(0.0, deadline - time.monotonic())))

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
            time.sleep(0.05)
    finally:
        close_udp_json_endpoint(intent_out)

    missing = ", ".join(sorted(pending)) or "<none>"
    raise SmokeSequenceError(
        f"timed out waiting for densi reset log token {_RESET_LOG_TOKEN!r} in {missing} "
        f"after {publish_count} publish cycles"
    )


def _bind_observer_telemetry_in(
    profile: SupervisorProfile,
) -> tuple[UdpTelemetryIn, tuple[str, int]]:
    last_error: OSError | None = None
    for addr in infer_observer_telemetry_candidates(profile):
        try:
            return UdpTelemetryIn.bind(addr), addr
        except OSError as exc:
            last_error = exc
            continue
    candidates = ", ".join(
        f"{host}:{port}" for host, port in infer_observer_telemetry_candidates(profile)
    )
    if last_error is not None:
        raise SmokeSequenceError(
            f"unable to bind smoke telemetry observer on any of [{candidates}]: {last_error}"
        )
    raise SmokeSequenceError(
        f"unable to infer smoke telemetry observer address from {profile.telem_in}"
    )


def _bind_hip_observer_telemetry_in(
    profile: SupervisorProfile,
) -> tuple[UdpTelemetryIn, tuple[str, int]]:
    last_error: OSError | None = None
    for addr in infer_hip_observer_telemetry_candidates(profile):
        try:
            return UdpTelemetryIn.bind(addr), addr
        except OSError as exc:
            last_error = exc
            continue
    candidates = ", ".join(
        f"{host}:{port}" for host, port in infer_hip_observer_telemetry_candidates(profile)
    )
    if last_error is not None:
        raise SmokeSequenceError(
            f"unable to bind HiP smoke telemetry observer on any of [{candidates}]: {last_error}"
        )
    raise SmokeSequenceError(
        f"unable to infer HiP smoke telemetry observer address from {profile.telem_in}"
    )


def _drive_resync_until_system_time_observed(
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

    observer_in, _observer_addr = _bind_observer_telemetry_in(profile)
    intent_out = UdpIntentOut.connect(parse_hostport(profile.intent_out))
    deadline = time.monotonic() + max(0.1, float(timeout_s))
    next_publish_at = time.monotonic()
    publish_every_s = max(0.05, float(publish_interval_s))
    settle = max(0.0, float(settle_s))
    publish_count = 0
    pending = {str(axis_id) for axis_id in axis_ids}
    first_by_axis: dict[str, str] = {}
    last_by_axis: dict[str, str] = {}
    first_tick_by_axis: dict[str, int] = {}
    last_tick_by_axis: dict[str, int] = {}
    try:
        while time.monotonic() < deadline:
            _raise_if_process_exited(
                process, "supervisor exited while observing running SystemTime after Resync"
            )
            now = time.monotonic()
            if now >= next_publish_at:
                for intent in intents:
                    intent_out.publish_intent(intent)
                publish_count += 1
                next_publish_at = now + publish_every_s
                if settle > 0.0:
                    time.sleep(min(settle, max(0.0, deadline - time.monotonic())))

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
            time.sleep(0.05)
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


def _drive_chk_es_taster_until_ready(
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

    observer_in, _observer_addr = _bind_observer_telemetry_in(profile)
    control_out = UdpDensiActionOut.connect(parse_hostport(supervisor_action_in_addr))

    axis_id_set = {str(axis_id) for axis_id in axis_ids}
    before_by_axis: dict[str, str] = {}
    first_active_by_axis: dict[str, str] = {}
    final_by_axis: dict[str, str] = {}
    armed_seen: set[str] = set()
    ready_seen: set[str] = set()
    publish_count = 0
    baseline_deadline = time.monotonic() + min(1.0, max(0.25, float(timeout_s) * 0.25))
    publish_every_s = max(0.05, float(publish_interval_s))
    settle = max(0.0, float(settle_s))
    ready_deadline = None
    next_publish_at = 0.0
    action = DensiRemoteAction("chk_es_taster", value=True)

    try:
        while time.monotonic() < baseline_deadline and len(before_by_axis) < len(axis_id_set):
            _raise_if_process_exited(
                process, "supervisor exited while observing pre-chkEsTaster idle state"
            )
            snaps = observer_in.drain_telemetry(limit=50)
            for snap in snaps:
                estates = extract_axis_estates(snap, axis_ids)
                for axis_id, estate in estates.items():
                    final_by_axis[axis_id] = estate
                    if axis_id not in before_by_axis and estate == "IDLE":
                        before_by_axis[axis_id] = estate
            time.sleep(0.05)

        ready_deadline = time.monotonic() + max(0.1, float(brake_grace_s) + 0.5)
        next_publish_at = time.monotonic()
        pending = set(axis_id_set)
        while time.monotonic() < ready_deadline:
            _raise_if_process_exited(
                process, "supervisor exited while observing chkEsTaster phase progression"
            )
            now = time.monotonic()
            if now >= next_publish_at:
                control_out.publish_action(action)
                publish_count += 1
                next_publish_at = now + publish_every_s
                if settle > 0.0:
                    time.sleep(min(settle, max(0.0, ready_deadline - time.monotonic())))

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
            time.sleep(0.05)
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


def _drive_motion_until_stopped(
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

    observer_in, _observer_addr = _bind_observer_telemetry_in(profile)
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
    baseline_deadline = time.monotonic() + min(1.5, max(0.5, float(timeout_s) * 0.25))
    start_command = InputdSimControl(action="start")
    publish_every_s = max(0.05, float(publish_interval_s))
    next_publish_at = time.monotonic()
    motion_deadline = time.monotonic() + max(0.5, float(timeout_s))

    try:
        while time.monotonic() < baseline_deadline and len(start_pos_by_axis) < len(axis_id_set):
            _raise_if_process_exited(
                process, "supervisor exited while observing pre-motion positions"
            )
            for snap in observer_in.drain_telemetry(limit=50):
                positions = extract_axis_positions(snap, axis_ids)
                for axis_id, pos in positions.items():
                    start_pos_by_axis.setdefault(axis_id, float(pos))
                    end_pos_by_axis[axis_id] = float(pos)
            time.sleep(0.05)
        if len(start_pos_by_axis) < len(axis_id_set):
            missing = ", ".join(sorted(axis_id_set - set(start_pos_by_axis))) or "<none>"
            raise SmokeSequenceError(f"timed out waiting for baseline positions in {missing}")

        while time.monotonic() < motion_deadline:
            _raise_if_process_exited(
                process, "supervisor exited while observing motion after chkEsTaster"
            )
            now = time.monotonic()
            if now >= next_publish_at and not axis_id_set.issubset(moving_axis_ids):
                control_out.publish_command(start_command)
                publish_count += 1
                next_publish_at = now + publish_every_s

            snaps = observer_in.drain_telemetry(limit=50)
            for snap in snaps:
                positions = extract_axis_positions(snap, axis_ids)
                velocities = extract_axis_velocities(snap, axis_ids)
                sample_time = time.monotonic()
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
            time.sleep(0.05)
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


def _drive_estart_until_observed(
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
    deadline = time.monotonic() + max(0.1, float(timeout_s))
    next_publish_at = time.monotonic()
    publish_every_s = max(0.05, float(publish_interval_s))
    settle = max(0.0, float(settle_s))

    tx_by_name = {
        target.densi_process_name: UdpDensiActionOut.connect(parse_hostport(target.action_out_addr))
        for target in targets
    }
    action = DensiRemoteAction("estart")
    try:
        while time.monotonic() < deadline:
            _raise_if_process_exited(
                process, "supervisor exited while observing densi ESStart logs"
            )
            now = time.monotonic()
            if now >= next_publish_at:
                for tx in tx_by_name.values():
                    tx.publish_action(action)
                publish_count += 1
                next_publish_at = now + publish_every_s
                if settle > 0.0:
                    time.sleep(min(settle, max(0.0, deadline - time.monotonic())))

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
            time.sleep(0.05)
    finally:
        for tx in tx_by_name.values():
            close_udp_json_endpoint(tx)

    missing = ", ".join(sorted(pending)) or "<none>"
    raise SmokeSequenceError(
        f"timed out waiting for densi ESStart log token {_ESTART_LOG_TOKEN!r} in {missing} "
        f"after {publish_count} publish cycles"
    )


def _wait_for_core_log_token(
    *,
    session_dir: Path,
    process: subprocess.Popen[str],
    token: str,
    timeout_s: float,
) -> None:
    deadline = time.monotonic() + max(0.1, float(timeout_s))
    while time.monotonic() < deadline:
        _raise_if_process_exited(process, "supervisor exited while waiting for core readiness")
        meta = _try_load_meta(session_dir)
        if meta is not None:
            child = meta.children.get("core")
            if child is not None and _log_contains_token(child, token):
                return
        time.sleep(0.05)
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


def _shutdown_supervisor_stack(launched: _LaunchedSupervisor) -> None:
    down_cmd = [
        sys.executable,
        "-m",
        "steuerung3d",
        "down",
        "--profile",
        os.fspath(launched.stack_profile_path),
    ]
    try:
        subprocess.run(down_cmd, cwd=Path.cwd(), text=True, check=False)
    except Exception:
        pass

    if launched.process.poll() is None:
        try:
            launched.process.terminate()
            launched.process.wait(timeout=5.0)
        except Exception:
            try:
                launched.process.kill()
            except Exception:
                pass


def _try_load_meta(session_dir: Path) -> StackMeta | None:
    try:
        return load_meta(session_dir)
    except Exception:
        return None


def _raise_if_process_exited(process: subprocess.Popen[str], prefix: str) -> None:
    rc = process.poll()
    if rc is None:
        return
    raise SmokeSequenceError(f"{prefix} (rc={rc})")


def _core_log_reports_owner(session_dir: Path, *, axis_id: str, hip_id: str) -> bool:
    core_log = session_dir / "core.log"
    try:
        text = core_log.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    axis_token_single = f"'{axis_id}'"
    axis_token_double = f'"{axis_id}"'
    owner_token_single = f"'owner': '{hip_id}'"
    owner_token_double = f'"owner": "{hip_id}"'
    for line in text.splitlines():
        if axis_token_single not in line and axis_token_double not in line:
            continue
        if owner_token_single in line or owner_token_double in line:
            return True
    return False


def _drive_open_hip_until_owned(
    *,
    profile: SupervisorProfile,
    process: subprocess.Popen[str],
    session_dir: Path,
    axis_id: str,
    supervisor_action_in_addr: str,
    hip_id: str,
    hip_smoke_control_base: int,
    timeout_s: float,
) -> tuple[HiPOpenObservation, int]:
    if not supervisor_action_in_addr:
        raise SmokeSequenceError("no supervisor smoke action input available for open_hip")
    axis_cfg = _axis_config_by_axis_id(profile, axis_id)
    if axis_cfg is None:
        raise SmokeSequenceError(f"axis {axis_id!r} not found for open_hip")
    control_out = UdpDensiActionOut.connect(parse_hostport(supervisor_action_in_addr))
    observer_in, _ = _bind_hip_observer_telemetry_in(profile)
    owner_before = ""
    owner_after = ""
    try:
        command = DensiRemoteAction(f"open_hip:{getattr(axis_cfg, 'unit_id', axis_id)}")
        control_out.publish_action(command)
        deadline = time.monotonic() + max(0.5, float(timeout_s))
        while time.monotonic() < deadline:
            _raise_if_process_exited(process, "supervisor exited while opening HiP")
            for snap in observer_in.drain_telemetry(limit=50):
                current_owner = extract_axis_owner(snap, axis_id)
                if not owner_before:
                    owner_before = current_owner
                if current_owner == hip_id:
                    owner_after = current_owner
                    return HiPOpenObservation(
                        axis_id=axis_id, owner_before=owner_before, owner_after=owner_after
                    ), 1
            if _core_log_reports_owner(session_dir, axis_id=axis_id, hip_id=hip_id):
                owner_after = hip_id
                return HiPOpenObservation(
                    axis_id=axis_id, owner_before=owner_before, owner_after=owner_after
                ), 1
            time.sleep(0.05)
    finally:
        close_udp_json_endpoint(observer_in)
        close_udp_json_endpoint(control_out)
    raise SmokeSequenceError(
        f"timed out waiting for axis {axis_id} to be owned by {hip_id!r} after open_hip"
    )


def _read_axis_param_baseline(
    *,
    profile: SupervisorProfile,
    process: subprocess.Popen[str],
    axis_id: str,
    param_name: str,
    timeout_s: float,
) -> float:
    observer_in, _ = _bind_hip_observer_telemetry_in(profile)
    try:
        deadline = time.monotonic() + max(0.5, float(timeout_s))
        while time.monotonic() < deadline:
            _raise_if_process_exited(process, "supervisor exited while reading parameter baseline")
            for snap in observer_in.drain_telemetry(limit=50):
                value = extract_axis_param_value(snap, axis_id, param_name)
                if value is not None:
                    return float(value)
            time.sleep(0.05)
    finally:
        close_udp_json_endpoint(observer_in)
    raise SmokeSequenceError(
        f"timed out waiting for baseline parameter {param_name!r} on axis {axis_id}"
    )


def _densi_log_reports_param_apply(
    session_dir: Path, *, axis_id: str, param_name: str, desired_value: float
) -> bool:
    log_path = session_dir / f"densi-{axis_id}.log"
    if not log_path.exists():
        return False
    try:
        tail = log_path.read_text(encoding="utf-8", errors="replace")[-20000:]
    except OSError:
        return False
    desired_tokens = {
        f"{param_name}={desired_value:g}",
        f"{param_name}={desired_value}",
    }
    if "param_write_applied" not in tail:
        return False
    if not any(token in tail for token in desired_tokens):
        return False
    return True


def _drive_hip_param_command_until_observed(
    *,
    axis_id: str,
    param_name: str,
    group: str,
    desired_value: float,
    hip_control_addr: str,
    session_dir: Path,
    profile: SupervisorProfile,
    process: subprocess.Popen[str],
    timeout_s: float,
) -> tuple[HiPParamObservation, int]:
    if not hip_control_addr:
        raise SmokeSequenceError("no HiP smoke control address available")
    control_out = UdpHiPSmokeControlOut.connect(parse_hostport(hip_control_addr))
    observer_in, _ = _bind_hip_observer_telemetry_in(profile)
    try:
        control_out.publish_command(
            HiPSmokeCommand(
                action="edit_write", group=group, values={param_name: float(desired_value)}
            )
        )
        deadline = time.monotonic() + max(0.5, float(timeout_s))
        while time.monotonic() < deadline:
            _raise_if_process_exited(
                process, "supervisor exited while waiting for HiP parameter write"
            )
            for snap in observer_in.drain_telemetry(limit=50):
                value = extract_axis_param_value(snap, axis_id, param_name)
                status = extract_axis_param_commit_status(snap, axis_id)
                status_norm = str(status).lower()
                if (
                    value is not None
                    and abs(float(value) - float(desired_value)) <= 1e-6
                    and status_norm == "applied"
                ):
                    return HiPParamObservation(
                        observed_value=float(value), commit_status=str(status)
                    ), 1
                if value is None and status_norm == "applied":
                    return HiPParamObservation(
                        observed_value=float(desired_value), commit_status=str(status)
                    ), 1
            if _densi_log_reports_param_apply(
                session_dir,
                axis_id=axis_id,
                param_name=param_name,
                desired_value=float(desired_value),
            ):
                return HiPParamObservation(
                    observed_value=float(desired_value), commit_status="applied(log)"
                ), 1
            time.sleep(0.05)
    finally:
        close_udp_json_endpoint(observer_in)
        close_udp_json_endpoint(control_out)
    raise SmokeSequenceError(
        f"timed out waiting for HiP parameter {param_name}={desired_value:g} to apply on axis {axis_id}"
    )


run_esreset_estart_sequence = run_esreset_estart_resync_sequence
