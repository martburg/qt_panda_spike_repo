from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, Optional

from steuerung3d.core.axis_id import normalize_axis_id
from steuerung3d.core.telemetry import TelemetrySnapshot

if TYPE_CHECKING:
    from .axis_router import AxisRouter


def ingest_device_telemetry(router: "AxisRouter", snaps: Iterable[TelemetrySnapshot]) -> None:
    for s in snaps:
        try:
            k: Optional[str] = None
            axes_keys = list(getattr(s, "axes", {}).keys())
            if len(axes_keys) == 1:
                k = normalize_axis_id(axes_keys[0])
            else:
                k = None
            if not k:
                continue

            router.last_dev_estop_word_by_axis[k] = int(getattr(s, "estop_status_word", 0))
            router.last_dev_params_by_axis[k] = dict(getattr(s, "params", {}) or {})
            router.last_dev_param_edit_active_by_axis[k] = bool(
                getattr(s, "param_edit_active", False)
            )
            router.last_dev_param_edit_group_by_axis[k] = str(getattr(s, "param_edit_group", ""))
            router.last_dev_plc_uplink_fields_by_axis[k] = {
                str(a): str(b) for a, b in dict(getattr(s, "plc_uplink_fields", {}) or {}).items()
            }
            router.last_dev_plc_uplink_tail_by_axis[k] = {
                str(a): str(b) for a, b in dict(getattr(s, "plc_uplink_tail", {}) or {}).items()
            }
            router.last_dev_param_commit_req_id_by_axis[k] = str(
                getattr(s, "param_commit_req_id", "")
            )
            router.last_dev_param_commit_group_by_axis[k] = str(
                getattr(s, "param_commit_group", "")
            )
            router.last_dev_param_commit_status_by_axis[k] = str(
                getattr(s, "param_commit_status", "idle")
            )
            router.last_dev_param_commit_age_ticks_by_axis[k] = int(
                getattr(s, "param_commit_age_ticks", 0)
            )
            router.last_dev_param_commit_unmatched_by_axis[k] = list(
                getattr(s, "param_commit_unmatched", []) or []
            )
        except Exception:
            continue
