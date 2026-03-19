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
    run_hip_param_sequence,
)


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description=(
            "Automate the supervisor HiP parameter smoke: start the supervisor stack, "
            "stop at synced IDLE, open one HiP, edit one safe parameter, and verify "
            "Densi-side acceptance."
        )
    )
    ap.add_argument(
        "--profile",
        default="configs/supervisor/smoke_2pairs_hip_param.toml",
        help=("Supervisor profile path (default: configs/supervisor/smoke_2pairs_hip_param.toml)"),
    )
    ap.add_argument(
        "--axis", default="", help="Axis id to open HiP for (default: first selected axis)."
    )
    ap.add_argument("--startup-timeout-s", type=float, default=20.0)
    ap.add_argument("--ready-grace-s", type=float, default=1.0)
    ap.add_argument("--observe-timeout-s", type=float, default=8.0)
    ap.add_argument("--settle-s", type=float, default=0.25)
    ap.add_argument("--publish-interval-s", type=float, default=0.25)
    ap.add_argument(
        "--no-restore",
        action="store_true",
        help="Do not restore the original parameter value after verifying the write.",
    )
    ap.add_argument(
        "--keep-running",
        action="store_true",
        help="Leave supervisor GUI + stack running after the HiP parameter step.",
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
        hip_param_axis_id=str(ns.axis or ""),
        hip_param_restore_after_write=not bool(ns.no_restore),
    )

    print(f"[smoke-hip] repo={REPO_ROOT}")
    print(f"[smoke-hip] supervisor profile={profile_path}")
    print("[smoke-hip] launching supervisor GUI + stack ...")
    try:
        result = run_hip_param_sequence(cfg)
    except SmokeSequenceError as exc:
        print(f"[smoke-hip] ERROR: {exc}")
        return 1

    print(f"[smoke-hip] session={result.session_dir}")
    print(f"[smoke-hip] selected axes={', '.join(result.selected_axis_ids) or '<none>'}")
    print(f"[smoke-hip] axis={result.axis_id} hip_id={result.hip_id}")
    print(f"[smoke-hip] reset publish cycles={result.reset_publish_count}")
    print(f"[smoke-hip] estart publish cycles={result.estart_publish_count}")
    print(f"[smoke-hip] resync publish cycles={result.resync_publish_count}")
    print(f"[smoke-hip] open hip commands={result.open_hip_command_count}")
    print(f"[smoke-hip] param commands={result.param_command_count}")
    print(f"[smoke-hip] restore commands={result.param_restore_command_count}")
    print(
        "[smoke-hip] observed reset logs="
        + (", ".join(result.observed_reset_log_names) or "<none>")
    )
    print(
        "[smoke-hip] observed estart logs="
        + (", ".join(result.observed_estart_log_names) or "<none>")
    )
    print(
        "[smoke-hip] observed running system time axes="
        + (", ".join(result.observed_system_time_axis_ids) or "<none>")
    )
    print(
        f"[smoke-hip] owner {result.axis_id}: before={result.owner_before or '<none>'} "
        f"after_open={result.owner_after_open or '<none>'}"
    )
    print(
        f"[smoke-hip] param {result.parameter_group}.{result.parameter_name}: "
        f"original={result.original_value:g} edited={result.edited_value:g} "
        f"observed_after_write={result.observed_value_after_write:g} "
        f"status_after_write={result.observed_commit_status_after_write or '<none>'}"
    )
    if result.restored:
        print(
            f"[smoke-hip] restore {result.parameter_name}: "
            f"observed_after_restore={result.observed_value_after_restore:g} "
            f"status_after_restore={result.observed_commit_status_after_restore or '<none>'}"
        )
    print(
        "[smoke-hip] ESReset + ESStart + Resync + HiP open + parameter roundtrip steps succeeded."
    )
    if cfg.keep_running:
        print("[smoke-hip] stack left running by request (--keep-running).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
