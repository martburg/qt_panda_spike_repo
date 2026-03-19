from __future__ import annotations

import subprocess
from pathlib import Path

from steuerung3d.apps.hi_p.smoke_control import HiPSmokeCommand, UdpHiPSmokeControlOut
from steuerung3d.core.net import parse_hostport
from steuerung3d.protocol.udp_channels import close_udp_json_endpoint

from .actions_transport import UdpDensiActionOut
from .models import DensiRemoteAction, SupervisorProfile
from .smoke_sequence_bootstrap import (
    _raise_if_process_exited,
    axis_config_by_axis_id,
    bind_hip_observer_telemetry_in,
    bootstrap_to_idle_synced,
    infer_hip_smoke_control_addr,
    select_safe_hip_param_spec,
    shutdown_supervisor_stack,
)
from .smoke_sequence_extract import (
    extract_axis_owner,
    extract_axis_param_commit_status,
    extract_axis_param_value,
)
from .smoke_sequence_polling import monotonic_deadline, poll_until_result
from .smoke_sequence_types import (
    HiPOpenObservation,
    HiPParamObservation,
    HiPParamSmokeResult,
    SmokeSequenceConfig,
    SmokeSequenceError,
)


def run_hip_param_sequence(config: SmokeSequenceConfig) -> HiPParamSmokeResult:
    boot = bootstrap_to_idle_synced(config)
    launched = boot.launched
    axis_id = str(
        config.hip_param_axis_id or (boot.selected_axis_ids[0] if boot.selected_axis_ids else "")
    )
    if not axis_id:
        raise SmokeSequenceError("no axis available for HiP parameter smoke scenario")
    axis_cfg = axis_config_by_axis_id(launched.profile, axis_id)
    if axis_cfg is None:
        raise SmokeSequenceError(f"axis {axis_id!r} not found in supervisor profile")
    hip_id = str(getattr(axis_cfg, "hip_id", "") or "")
    if not hip_id:
        raise SmokeSequenceError(f"axis {axis_id!r} has no hip_id configured")
    spec = select_safe_hip_param_spec()
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
            shutdown_supervisor_stack(launched)


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
    del hip_smoke_control_base
    if not supervisor_action_in_addr:
        raise SmokeSequenceError("no supervisor smoke action input available for open_hip")
    axis_cfg = axis_config_by_axis_id(profile, axis_id)
    if axis_cfg is None:
        raise SmokeSequenceError(f"axis {axis_id!r} not found for open_hip")
    control_out = UdpDensiActionOut.connect(parse_hostport(supervisor_action_in_addr))
    observer_in, _ = bind_hip_observer_telemetry_in(profile)
    owner_before = ""
    owner_after = ""
    try:
        command = DensiRemoteAction(f"open_hip:{getattr(axis_cfg, 'unit_id', axis_id)}")
        control_out.publish_action(command)
        deadline = monotonic_deadline(timeout_s, minimum_s=0.5)

        def _observe() -> HiPOpenObservation | None:
            nonlocal owner_before, owner_after
            for snap in observer_in.drain_telemetry(limit=50):
                current_owner = extract_axis_owner(snap, axis_id)
                if not owner_before:
                    owner_before = current_owner
                if current_owner == hip_id:
                    owner_after = current_owner
                    return HiPOpenObservation(
                        axis_id=axis_id, owner_before=owner_before, owner_after=owner_after
                    )
            if _core_log_reports_owner(session_dir, axis_id=axis_id, hip_id=hip_id):
                owner_after = hip_id
                return HiPOpenObservation(
                    axis_id=axis_id, owner_before=owner_before, owner_after=owner_after
                )
            return None

        result = poll_until_result(
            deadline=deadline,
            check_alive=lambda: _raise_if_process_exited(
                process, "supervisor exited while opening HiP"
            ),
            observe=_observe,
        )
        if result is not None:
            return result, 1
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
    observer_in, _ = bind_hip_observer_telemetry_in(profile)
    try:
        deadline = monotonic_deadline(timeout_s, minimum_s=0.5)

        def _observe() -> float | None:
            for snap in observer_in.drain_telemetry(limit=50):
                value = extract_axis_param_value(snap, axis_id, param_name)
                if value is not None:
                    return float(value)
            return None

        result = poll_until_result(
            deadline=deadline,
            check_alive=lambda: _raise_if_process_exited(
                process, "supervisor exited while reading parameter baseline"
            ),
            observe=_observe,
        )
        if result is not None:
            return result
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
    observer_in, _ = bind_hip_observer_telemetry_in(profile)
    try:
        control_out.publish_command(
            HiPSmokeCommand(
                action="edit_write", group=group, values={param_name: float(desired_value)}
            )
        )
        deadline = monotonic_deadline(timeout_s, minimum_s=0.5)

        def _observe() -> HiPParamObservation | None:
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
                    )
                if value is None and status_norm == "applied":
                    return HiPParamObservation(
                        observed_value=float(desired_value), commit_status=str(status)
                    )
            if _densi_log_reports_param_apply(
                session_dir,
                axis_id=axis_id,
                param_name=param_name,
                desired_value=float(desired_value),
            ):
                return HiPParamObservation(
                    observed_value=float(desired_value), commit_status="applied(log)"
                )
            return None

        result = poll_until_result(
            deadline=deadline,
            check_alive=lambda: _raise_if_process_exited(
                process, "supervisor exited while waiting for HiP parameter write"
            ),
            observe=_observe,
        )
        if result is not None:
            return result, 1
    finally:
        close_udp_json_endpoint(observer_in)
        close_udp_json_endpoint(control_out)
    raise SmokeSequenceError(
        f"timed out waiting for HiP parameter {param_name}={desired_value:g} to apply on axis {axis_id}"
    )
