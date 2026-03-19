from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if os.fspath(SRC_ROOT) not in sys.path:
    sys.path.insert(0, os.fspath(SRC_ROOT))

from steuerung3d.apps.supervisor.smoke_sequence_support import (  # noqa: E402
    SmokeSequenceConfig,
    SmokeSequenceError,
    run_esreset_estart_resync_sequence,
)


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description=(
            "Automate the current supervisor smoke slices: start the supervisor stack, "
            "wait for core+densi+inputd_sim, issue ESReset, ESStart, Resync, then "
            "chkEsTaster and scripted deadman/velocity motion."
        )
    )
    ap.add_argument(
        "--profile",
        default="configs/supervisor/smoke_2pairs_motion.toml",
        help=("Supervisor profile path (default: configs/supervisor/smoke_2pairs_motion.toml)"),
    )
    ap.add_argument("--startup-timeout-s", type=float, default=20.0)
    ap.add_argument("--ready-grace-s", type=float, default=1.0)
    ap.add_argument("--observe-timeout-s", type=float, default=8.0)
    ap.add_argument("--settle-s", type=float, default=0.25)
    ap.add_argument("--publish-interval-s", type=float, default=0.25)
    ap.add_argument("--brake-grace-s", type=float, default=2.0)
    ap.add_argument("--motion-pos-delta-min", type=float, default=0.2)
    ap.add_argument("--motion-vel-move-eps", type=float, default=0.05)
    ap.add_argument("--motion-vel-zero-eps", type=float, default=0.05)
    ap.add_argument("--motion-release-settle-s", type=float, default=0.5)
    ap.add_argument(
        "--keep-running",
        action="store_true",
        help="Leave supervisor GUI + stack running after the motion step.",
    )
    return ap


def main(argv: list[str] | None = None) -> int:
    ns = _build_parser().parse_args(argv)
    os.chdir(REPO_ROOT)
    profile_path = (
        (REPO_ROOT / str(ns.profile)).resolve()
        if not Path(ns.profile).is_absolute()
        else Path(ns.profile)
    )

    cfg = SmokeSequenceConfig(
        supervisor_profile_path=profile_path,
        startup_timeout_s=float(ns.startup_timeout_s),
        ready_grace_s=float(ns.ready_grace_s),
        observe_timeout_s=float(ns.observe_timeout_s),
        settle_s=float(ns.settle_s),
        publish_interval_s=float(ns.publish_interval_s),
        keep_running=bool(ns.keep_running),
        brake_grace_s=float(ns.brake_grace_s),
        motion_pos_delta_min=float(ns.motion_pos_delta_min),
        motion_vel_move_eps=float(ns.motion_vel_move_eps),
        motion_vel_zero_eps=float(ns.motion_vel_zero_eps),
        motion_release_settle_s=float(ns.motion_release_settle_s),
    )

    print(f"[smoke] repo={REPO_ROOT}")
    print(f"[smoke] supervisor profile={profile_path}")
    print("[smoke] launching supervisor GUI + stack ...")
    try:
        result = run_esreset_estart_resync_sequence(cfg)
    except SmokeSequenceError as exc:
        print(f"[smoke] ERROR: {exc}")
        return 1

    print(f"[smoke] session={result.session_dir}")
    print(f"[smoke] selected axes={', '.join(result.selected_axis_ids) or '<none>'}")
    print(f"[smoke] reset publish cycles={result.reset_publish_count}")
    print("[smoke] observed reset logs=" + (", ".join(result.observed_reset_log_names) or "<none>"))
    print(f"[smoke] estart publish cycles={result.estart_publish_count}")
    print(f"[smoke] resync publish cycles={result.resync_publish_count}")
    print(
        "[smoke] observed estart logs=" + (", ".join(result.observed_estart_log_names) or "<none>")
    )
    print(
        "[smoke] observed running system time axes="
        + (", ".join(result.observed_system_time_axis_ids) or "<none>")
    )
    print(f"[smoke] chkEsTaster publish cycles={result.chk_taster_publish_count}")
    print(
        "[smoke] observed chk ready axes="
        + (", ".join(result.observed_chk_ready_axis_ids) or "<none>")
    )
    print(f"[smoke] motion start commands={result.motion_command_publish_count}")
    print(
        "[smoke] observed motion axes=" + (", ".join(result.observed_motion_axis_ids) or "<none>")
    )
    print("[smoke] observed stop axes=" + (", ".join(result.observed_stop_axis_ids) or "<none>"))
    first_by_axis = dict(result.system_time_first_by_axis or {})
    last_by_axis = dict(result.system_time_last_by_axis or {})
    first_tick_by_axis = dict(result.system_time_first_tick_by_axis or {})
    last_tick_by_axis = dict(result.system_time_last_tick_by_axis or {})
    chk_before = dict(result.chk_phase_before_by_axis or {})
    chk_first = dict(result.chk_phase_first_active_by_axis or {})
    chk_final = dict(result.chk_phase_final_by_axis or {})
    chk_armed = set(result.chk_armed_axis_ids or ())
    chk_ready = set(result.chk_ready_axis_ids or ())
    motion_start = dict(result.motion_start_pos_by_axis or {})
    motion_end = dict(result.motion_end_pos_by_axis or {})
    motion_delta = dict(result.motion_delta_by_axis or {})
    motion_max_abs_vel = dict(result.motion_max_abs_vel_by_axis or {})
    motion_final_abs_vel = dict(result.motion_final_abs_vel_by_axis or {})
    for axis_id in result.selected_axis_ids:
        first_tok = first_by_axis.get(axis_id, "<none>")
        last_tok = last_by_axis.get(axis_id, "<none>")
        first_tick = first_tick_by_axis.get(axis_id, 0)
        last_tick = last_tick_by_axis.get(axis_id, 0)
        print(
            f"[smoke] system time {axis_id}: {first_tok} -> {last_tok} "
            f"[device_tick {first_tick} -> {last_tick}]"
        )
        print(
            f"[smoke] chk phase {axis_id}: before={chk_before.get(axis_id, '<none>')} "
            f"first_active={chk_first.get(axis_id, '<none>')} "
            f"final={chk_final.get(axis_id, '<none>')} "
            f"armed_seen={axis_id in chk_armed} ready_seen={axis_id in chk_ready}"
        )
        print(
            f"[smoke] motion {axis_id}: start={motion_start.get(axis_id, 0.0):.3f} "
            f"end={motion_end.get(axis_id, 0.0):.3f} "
            f"delta={motion_delta.get(axis_id, 0.0):.3f} "
            f"max_abs_vel={motion_max_abs_vel.get(axis_id, 0.0):.3f} "
            f"final_abs_vel={motion_final_abs_vel.get(axis_id, 0.0):.3f}"
        )
    print(
        "[smoke] ESReset + ESStart + Resync + running SystemTime + chkEsTaster + motion steps succeeded."
    )
    if cfg.keep_running:
        print("[smoke] stack left running by request (--keep-running).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
