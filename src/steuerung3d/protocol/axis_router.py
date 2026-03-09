from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Optional, Protocol, Sequence, cast

from steuerung3d.core.axis_id import normalize_axis_id
from steuerung3d.core.command_frame import CommandFrame, ParamOp, coerce_param_ops
from steuerung3d.core.joy_state import JoyState
from steuerung3d.core.telemetry import TelemetrySnapshot


class CommandFrameSink(Protocol):
    def publish_command_frame(self, frame: CommandFrame) -> None: ...


class TelemetrySink(Protocol):
    def publish_telemetry(self, snap: TelemetrySnapshot) -> None: ...


def _empty_telemetry_sinks() -> list[TelemetrySink]:
    return []


def _make_snapshot(**kwargs: Any) -> TelemetrySnapshot:
    ctor = cast(Any, TelemetrySnapshot)
    return ctor(**kwargs)


@dataclass
class AxisRouter:
    """Strict per-axis routing and slicing.

    This is a small but important seam:
      - Core builds *multi-axis* CommandFrame and TelemetrySnapshot.
      - Device adapters and HiP UI instances are axis-scoped.

    The router centralizes all per-axis shaping:
      - CommandFrame is reduced to a single-axis frame per device.
      - CommandFrame.lifetick_echo is reduced to the addressed axis.
      - TelemetrySnapshot is sliced to a single axis for each UI target.
      - Device-scoped fields (params/estop word/param commit state) are pinned
        per axis via caches updated from device telemetry.
    """

    axis_ids: Sequence[str]
    dev_cmd_out_by_axis: Mapping[str, CommandFrameSink]
    ui_telem_out_by_axis: Mapping[str, TelemetrySink]
    ui_telem_fanout: list[TelemetrySink] = field(default_factory=_empty_telemetry_sinks)

    # --- device-scoped caches (multi-axis runs must pin these per axis) ---
    last_dev_params_by_axis: dict[str, dict[str, float]] = field(default_factory=lambda: {})
    last_dev_estop_word_by_axis: dict[str, int] = field(default_factory=lambda: {})
    last_dev_param_edit_active_by_axis: dict[str, bool] = field(default_factory=lambda: {})
    last_dev_param_edit_group_by_axis: dict[str, str] = field(default_factory=lambda: {})

    # Raw PLC uplink payload caches (per axis). HiP may consume these directly.
    last_dev_plc_uplink_fields_by_axis: dict[str, dict[str, str]] = field(
        default_factory=lambda: {}
    )
    last_dev_plc_uplink_tail_by_axis: dict[str, dict[str, str]] = field(default_factory=lambda: {})

    last_dev_param_commit_req_id_by_axis: dict[str, str] = field(default_factory=lambda: {})
    last_dev_param_commit_group_by_axis: dict[str, str] = field(default_factory=lambda: {})
    last_dev_param_commit_status_by_axis: dict[str, str] = field(default_factory=lambda: {})
    last_dev_param_commit_age_ticks_by_axis: dict[str, int] = field(default_factory=lambda: {})
    last_dev_param_commit_unmatched_by_axis: dict[str, list[str]] = field(
        default_factory=lambda: {}
    )

    def __post_init__(self) -> None:
        # Canonicalize axis ids at the boundary so downstream dict keys stay stable.
        self.axis_ids = [
            normalize_axis_id(a) for a in (self.axis_ids or []) if normalize_axis_id(a)
        ]

        # Keep routing dicts aligned to the canonical ids.
        self.dev_cmd_out_by_axis = {
            normalize_axis_id(k): v
            for k, v in dict(self.dev_cmd_out_by_axis or {}).items()
            if normalize_axis_id(k)
        }
        self.ui_telem_out_by_axis = {
            normalize_axis_id(k): v
            for k, v in dict(self.ui_telem_out_by_axis or {}).items()
            if normalize_axis_id(k)
        }
        fanout: list[TelemetrySink] = list(self.ui_telem_fanout or [])
        self.ui_telem_fanout = fanout

    # --------------------
    # Command routing
    # --------------------
    def publish_command_frames(
        self,
        cmd_frame: CommandFrame,
        *,
        estop_reset_by_axis: Optional[Mapping[str, bool]] = None,
        param_ops_by_axis: Optional[Mapping[str, list[ParamOp]]] = None,
    ) -> int:
        """Route a multi-axis CommandFrame into one command per axis.

        Returns number of frames published.
        """
        estop_reset_by_axis = estop_reset_by_axis or {}
        param_ops_by_axis = param_ops_by_axis or {}

        sent = 0
        for axis_id in self.axis_ids:
            sp = cmd_frame.axes.get(axis_id)
            if sp is None:
                continue

            # Reduce echo-map to this device.
            echo_val: int | None = None
            try:
                raw_echo_map = getattr(cmd_frame, "lifetick_echo", {}) or {}
                echo_map = (
                    cast(dict[str, object], raw_echo_map) if isinstance(raw_echo_map, dict) else {}
                )
                raw_echo_val = echo_map.get(axis_id)
                if isinstance(raw_echo_val, (int, float, str)):
                    echo_val = int(raw_echo_val)
            except Exception:
                echo_val = None
            lifetick_echo_axis = {axis_id: (echo_val & 0xFFFF)} if echo_val is not None else {}

            resync_map = getattr(cmd_frame, "resync_by_axis", {}) or {}
            resync_axis = bool(resync_map.get(axis_id, False))
            # Legacy fallback: only honor the flat bit in true single-axis frames.
            if not resync_axis and len(getattr(cmd_frame, "axes", {}) or {}) == 1:
                resync_axis = bool(getattr(cmd_frame, "resync", False))

            frame_axis = CommandFrame(
                tick=cmd_frame.tick,
                t_s=cmd_frame.t_s,
                estop=cmd_frame.estop,
                fault=cmd_frame.fault,
                core_mode=cmd_frame.core_mode,
                axes={axis_id: sp},
                intent=bool(getattr(cmd_frame, "intent", True)),
                resync=resync_axis,
                gui_not_halt=bool(getattr(cmd_frame, "gui_not_halt", False)),
                lifetick_echo=lifetick_echo_axis,
                resync_by_axis={axis_id: True} if resync_axis else {},
                estop_reset=bool(estop_reset_by_axis.get(axis_id, False)),
                param_ops=coerce_param_ops(param_ops_by_axis.get(axis_id, [])),
                main_reset_by_axis={
                    axis_id: bool(getattr(cmd_frame, "main_reset_by_axis", {}).get(axis_id, False))
                },
                guider_reset_by_axis={
                    axis_id: bool(
                        getattr(cmd_frame, "guider_reset_by_axis", {}).get(axis_id, False)
                    )
                },
            )

            out = self.dev_cmd_out_by_axis.get(axis_id)
            if out is None:
                continue
            out.publish_command_frame(frame_axis)
            sent += 1
        return sent

    # --------------------
    # Device telemetry ingestion (update caches)
    # --------------------
    def ingest_device_telemetry(self, snaps: Iterable[TelemetrySnapshot]) -> None:
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

                self.last_dev_estop_word_by_axis[k] = int(getattr(s, "estop_status_word", 0))
                self.last_dev_params_by_axis[k] = dict(getattr(s, "params", {}) or {})
                self.last_dev_param_edit_active_by_axis[k] = bool(
                    getattr(s, "param_edit_active", False)
                )
                self.last_dev_param_edit_group_by_axis[k] = str(getattr(s, "param_edit_group", ""))

                # Raw PLC uplink payload (pre/post EOD). Keep as strings.
                self.last_dev_plc_uplink_fields_by_axis[k] = {
                    str(a): str(b)
                    for a, b in dict(getattr(s, "plc_uplink_fields", {}) or {}).items()
                }
                self.last_dev_plc_uplink_tail_by_axis[k] = {
                    str(a): str(b) for a, b in dict(getattr(s, "plc_uplink_tail", {}) or {}).items()
                }

                self.last_dev_param_commit_req_id_by_axis[k] = str(
                    getattr(s, "param_commit_req_id", "")
                )
                self.last_dev_param_commit_group_by_axis[k] = str(
                    getattr(s, "param_commit_group", "")
                )
                self.last_dev_param_commit_status_by_axis[k] = str(
                    getattr(s, "param_commit_status", "idle")
                )
                self.last_dev_param_commit_age_ticks_by_axis[k] = int(
                    getattr(s, "param_commit_age_ticks", 0)
                )
                self.last_dev_param_commit_unmatched_by_axis[k] = list(
                    getattr(s, "param_commit_unmatched", []) or []
                )
            except Exception:
                continue

    # --------------------
    # UI telemetry slicing
    # --------------------
    def slice_snapshot_for_axis(self, snap: TelemetrySnapshot, axis_id: str) -> TelemetrySnapshot:
        ax_t = dict(getattr(snap, "axes", {})).get(axis_id)
        axes = {axis_id: ax_t} if ax_t is not None else {}

        densis = dict(getattr(snap, "densis", {}))
        densis_one = {axis_id: densis[axis_id]} if axis_id in densis else {}

        lease_axis = dict(getattr(snap, "lease_axis", {}) or {})
        lease_one = {axis_id: lease_axis[axis_id]} if axis_id in lease_axis else {}

        return _make_snapshot(
            tick=int(getattr(snap, "tick", 0)),
            t_s=float(getattr(snap, "t_s", 0.0)),
            core_mode=str(getattr(snap, "core_mode", "")),
            estop=bool(getattr(snap, "estop", False)),
            fault=bool(getattr(snap, "fault", False)),
            axes=axes,
            rig_mode=str(getattr(snap, "rig_mode", "DISCOVERY")),
            densis=densis_one,
            lease_rig=str(getattr(snap, "lease_rig", "")),
            lease_axis=lease_one,
            estop_status_word=int(
                self.last_dev_estop_word_by_axis.get(
                    axis_id, int(getattr(snap, "estop_status_word", 0))
                )
            ),
            param_edit_active=bool(
                self.last_dev_param_edit_active_by_axis.get(
                    axis_id, bool(getattr(snap, "param_edit_active", False))
                )
            ),
            param_edit_group=str(
                self.last_dev_param_edit_group_by_axis.get(
                    axis_id, str(getattr(snap, "param_edit_group", ""))
                )
            ),
            params=dict(
                self.last_dev_params_by_axis.get(axis_id, dict(getattr(snap, "params", {})) or {})
            ),
            plc_uplink_fields=dict(
                self.last_dev_plc_uplink_fields_by_axis.get(
                    axis_id, dict(getattr(snap, "plc_uplink_fields", {})) or {}
                )
            ),
            plc_uplink_tail=dict(
                self.last_dev_plc_uplink_tail_by_axis.get(
                    axis_id, dict(getattr(snap, "plc_uplink_tail", {})) or {}
                )
            ),
            core_acks=list(getattr(snap, "core_acks", [])),
            param_commit_req_id=str(
                self.last_dev_param_commit_req_id_by_axis.get(
                    axis_id, str(getattr(snap, "param_commit_req_id", ""))
                )
            ),
            param_commit_group=str(
                self.last_dev_param_commit_group_by_axis.get(
                    axis_id, str(getattr(snap, "param_commit_group", ""))
                )
            ),
            param_commit_status=str(
                self.last_dev_param_commit_status_by_axis.get(
                    axis_id, str(getattr(snap, "param_commit_status", "idle"))
                )
            ),
            param_commit_age_ticks=int(
                self.last_dev_param_commit_age_ticks_by_axis.get(
                    axis_id, int(getattr(snap, "param_commit_age_ticks", 0))
                )
            ),
            param_commit_unmatched=list(
                self.last_dev_param_commit_unmatched_by_axis.get(
                    axis_id, list(getattr(snap, "param_commit_unmatched", [])) or []
                )
            ),
            joy=getattr(snap, "joy", JoyState()),
        )

    def _project_joy_for_axis(self, snap: TelemetrySnapshot, axis_id: str) -> JoyState:
        joy = getattr(snap, "joy", JoyState())
        if not isinstance(joy, JoyState):
            joy = JoyState()
        return JoyState(
            deadman=bool(getattr(joy, "deadman", False)),
            select_hip=normalize_axis_id(axis_id) in tuple(getattr(joy, "selected_axes", ()) or ()),
            soll_speed=float(getattr(joy, "soll_speed", 0.0)),
            selected_axes=getattr(joy, "selected_axes", ()),
        )

    def fanout_snapshot_with_axis_caches(self, snap: TelemetrySnapshot) -> TelemetrySnapshot:
        return _make_snapshot(
            tick=int(getattr(snap, "tick", 0)),
            t_s=float(getattr(snap, "t_s", 0.0)),
            core_mode=str(getattr(snap, "core_mode", "")),
            estop=bool(getattr(snap, "estop", False)),
            fault=bool(getattr(snap, "fault", False)),
            axes=dict(getattr(snap, "axes", {}) or {}),
            rig_mode=str(getattr(snap, "rig_mode", "DISCOVERY")),
            densis=dict(getattr(snap, "densis", {}) or {}),
            lease_rig=str(getattr(snap, "lease_rig", "")),
            lease_axis=dict(getattr(snap, "lease_axis", {}) or {}),
            lease_rig_holder=str(getattr(snap, "lease_rig_holder", getattr(snap, "lease_rig", ""))),
            lease_axis_holders=dict(getattr(snap, "lease_axis_holders", {}) or {}),
            lease_denial_reason=str(getattr(snap, "lease_denial_reason", "")),
            estop_status_word=int(getattr(snap, "estop_status_word", 0)),
            param_edit_active=bool(getattr(snap, "param_edit_active", False)),
            param_edit_group=str(getattr(snap, "param_edit_group", "")),
            params=dict(getattr(snap, "params", {}) or {}),
            plc_uplink_fields=dict(getattr(snap, "plc_uplink_fields", {}) or {}),
            plc_uplink_tail=dict(getattr(snap, "plc_uplink_tail", {}) or {}),
            axis_estop_status_word={
                str(k): int(v) for k, v in dict(self.last_dev_estop_word_by_axis or {}).items()
            },
            axis_param_edit_active={
                str(k): bool(v)
                for k, v in dict(self.last_dev_param_edit_active_by_axis or {}).items()
            },
            axis_param_edit_group={
                str(k): str(v)
                for k, v in dict(self.last_dev_param_edit_group_by_axis or {}).items()
            },
            axis_params={
                str(k): dict(v or {}) for k, v in dict(self.last_dev_params_by_axis or {}).items()
            },
            axis_plc_uplink_fields={
                str(k): dict(v or {})
                for k, v in dict(self.last_dev_plc_uplink_fields_by_axis or {}).items()
            },
            axis_plc_uplink_tail={
                str(k): dict(v or {})
                for k, v in dict(self.last_dev_plc_uplink_tail_by_axis or {}).items()
            },
            axis_param_commit_req_id={
                str(k): str(v)
                for k, v in dict(self.last_dev_param_commit_req_id_by_axis or {}).items()
            },
            axis_param_commit_group={
                str(k): str(v)
                for k, v in dict(self.last_dev_param_commit_group_by_axis or {}).items()
            },
            axis_param_commit_status={
                str(k): str(v)
                for k, v in dict(self.last_dev_param_commit_status_by_axis or {}).items()
            },
            axis_param_commit_age_ticks={
                str(k): int(v)
                for k, v in dict(self.last_dev_param_commit_age_ticks_by_axis or {}).items()
            },
            axis_param_commit_unmatched={
                str(k): list(v or [])
                for k, v in dict(self.last_dev_param_commit_unmatched_by_axis or {}).items()
            },
            core_acks=list(getattr(snap, "core_acks", [])),
            param_commit_req_id=str(getattr(snap, "param_commit_req_id", "")),
            param_commit_group=str(getattr(snap, "param_commit_group", "")),
            param_commit_status=str(getattr(snap, "param_commit_status", "idle")),
            param_commit_age_ticks=int(getattr(snap, "param_commit_age_ticks", 0)),
            param_commit_unmatched=list(getattr(snap, "param_commit_unmatched", []) or []),
            joy=getattr(snap, "joy", JoyState()),
        )

    def publish_ui_snapshot(self, snap: TelemetrySnapshot) -> int:
        sent = 0
        if self.ui_telem_fanout:
            fanout_snap = self.fanout_snapshot_with_axis_caches(snap)
            _diag_log = logging.getLogger("axis_router")
            densis_dbg: dict[str, dict[str, str | bool]] = {}
            for k, d in dict(getattr(fanout_snap, "densis", {}) or {}).items():
                densis_dbg[str(k)] = {
                    "online": bool(getattr(d, "online", False)),
                    "owner": str(getattr(d, "claimed_by_hip", "") or ""),
                }
            for tx in self.ui_telem_fanout:
                target = getattr(getattr(getattr(tx, "tx", None), "link", None), "target", None)
                _diag_log.info(
                    "ui fanout tx target=%s tick=%s core_mode=%s estop=%s fault=%s densis=%s",
                    target,
                    getattr(fanout_snap, "tick", None),
                    getattr(fanout_snap, "core_mode", None),
                    getattr(fanout_snap, "estop", None),
                    getattr(fanout_snap, "fault", None),
                    densis_dbg,
                )
                tx.publish_telemetry(fanout_snap)
                sent += 1
            return sent

        for axis_id in self.axis_ids:
            tx = self.ui_telem_out_by_axis.get(axis_id)
            if tx is None:
                continue
            tx.publish_telemetry(self.slice_snapshot_for_axis(snap, axis_id))
            sent += 1
        return sent
