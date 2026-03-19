from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

from steuerung3d.apps.hi_p.smoke_param_specs import SAFE_HIP_SMOKE_PARAMS, HiPSmokeParamSpec
from steuerung3d.apps.inputd_sim.config import load_inputd_sim_config
from steuerung3d.core.process_liveness import pid_is_alive
from steuerung3d.core.stack_loader import load_stack_profile
from steuerung3d.core.stack_meta import StackMeta, find_latest_session_dir, load_meta
from steuerung3d.core.stack_spec import StackSpec
from steuerung3d.protocol.udp_channels import UdpTelemetryIn

from .models import SupervisorProfile
from .profile_loader import load_profile
from .smoke_sequence_extract import (
    infer_hip_observer_telemetry_candidates,
    infer_observer_telemetry_candidates,
)
from .smoke_sequence_types import (
    _CORE_IDLE_TOKEN,
    _HIP_SMOKE_CONTROL_BASE,
    IdleSyncedBootstrap,
    SmokeSequenceConfig,
    SmokeSequenceError,
    _LaunchedSupervisor,
)


def axis_config_by_axis_id(profile: SupervisorProfile, axis_id: str) -> object | None:
    for axis in profile.axes:
        if str(axis.axis_id) == str(axis_id):
            return axis
    return None


def infer_hip_smoke_control_addr(profile: SupervisorProfile, axis_id: str, *, base: int) -> str:
    for idx, axis in enumerate(profile.axes):
        if str(axis.axis_id) == str(axis_id):
            return f"127.0.0.1:{int(base) + idx}"
    return ""


def select_safe_hip_param_spec(name: str = "") -> HiPSmokeParamSpec:
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


def launch_supervisor(config: SmokeSequenceConfig) -> _LaunchedSupervisor:
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


def bootstrap_to_idle_synced(config: SmokeSequenceConfig) -> IdleSyncedBootstrap:
    from .smoke_sequence_drive import (
        drive_estart_until_observed,
        drive_estop_reset_until_observed,
        drive_resync_until_system_time_observed,
        wait_for_core_log_token,
    )
    from .smoke_sequence_targets import (
        build_selected_estop_reset_intents,
        densi_process_names_for_axes,
    )

    launched = launch_supervisor(config)
    try:
        if config.ready_grace_s > 0.0:
            time.sleep(float(config.ready_grace_s))
        selected_axis_ids = tuple(
            intent.axis_id for intent in build_selected_estop_reset_intents(launched.profile)
        )
        densi_names = densi_process_names_for_axes(selected_axis_ids)
        observed_reset, reset_publish_count = drive_estop_reset_until_observed(
            session_dir=launched.session_dir,
            process=launched.process,
            profile=launched.profile,
            densi_process_names=densi_names,
            timeout_s=float(config.observe_timeout_s),
            publish_interval_s=float(config.publish_interval_s),
            settle_s=float(config.settle_s),
        )
        wait_for_core_log_token(
            session_dir=launched.session_dir,
            process=launched.process,
            token=_CORE_IDLE_TOKEN,
            timeout_s=min(max(1.0, float(config.observe_timeout_s)), 5.0),
        )
        observed_estart, estart_publish_count = drive_estart_until_observed(
            session_dir=launched.session_dir,
            process=launched.process,
            profile=launched.profile,
            timeout_s=float(config.observe_timeout_s),
            publish_interval_s=float(config.publish_interval_s),
            settle_s=float(config.settle_s),
        )
        system_time_progress, resync_publish_count = drive_resync_until_system_time_observed(
            profile=launched.profile,
            process=launched.process,
            axis_ids=selected_axis_ids,
            timeout_s=float(config.observe_timeout_s),
            publish_interval_s=float(config.publish_interval_s),
            settle_s=float(config.settle_s),
        )
        return IdleSyncedBootstrap(
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
            shutdown_supervisor_stack(launched)
        raise


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


def bind_observer_telemetry_in(
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


def bind_hip_observer_telemetry_in(
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


def shutdown_supervisor_stack(launched: _LaunchedSupervisor) -> None:
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
