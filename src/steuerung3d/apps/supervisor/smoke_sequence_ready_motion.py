from __future__ import annotations

from .smoke_sequence_bootstrap import bootstrap_to_idle_synced, shutdown_supervisor_stack
from .smoke_sequence_drive import (
    drive_chk_es_taster_until_ready,
    drive_motion_until_stopped,
)
from .smoke_sequence_types import SmokeSequenceConfig, SmokeSequenceResult


def run_esreset_estart_resync_sequence(config: SmokeSequenceConfig) -> SmokeSequenceResult:
    boot = bootstrap_to_idle_synced(config)
    launched = boot.launched
    try:
        selected_axis_ids = boot.selected_axis_ids
        observed_reset = boot.observed_reset
        reset_publish_count = boot.reset_publish_count
        observed_estart = boot.observed_estart
        estart_publish_count = boot.estart_publish_count
        system_time_progress = boot.system_time_progress
        resync_publish_count = boot.resync_publish_count
        chk_taster_progress, chk_taster_publish_count = drive_chk_es_taster_until_ready(
            profile=launched.profile,
            process=launched.process,
            axis_ids=selected_axis_ids,
            supervisor_action_in_addr=launched.supervisor_action_in_addr,
            timeout_s=float(config.observe_timeout_s),
            publish_interval_s=float(config.publish_interval_s),
            settle_s=float(config.settle_s),
            brake_grace_s=float(config.brake_grace_s),
        )
        motion_progress, motion_command_publish_count = drive_motion_until_stopped(
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
            shutdown_supervisor_stack(launched)
