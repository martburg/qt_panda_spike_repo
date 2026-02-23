from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping, Optional, Protocol

from steuerung3d.core.command_frame import CommandFrame, ParamOp, coerce_param_ops
from steuerung3d.core.telemetry import TelemetrySnapshot
from steuerung3d.core.joy_state import JoyState


class CommandFrameSink(Protocol):
    def publish_command_frame(self, frame: CommandFrame) -> None: ...


class TelemetrySink(Protocol):
    def publish_telemetry(self, snap: TelemetrySnapshot) -> None: ...


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

    axis_ids: List[str]
    dev_cmd_out_by_axis: Dict[str, CommandFrameSink]
    ui_telem_out_by_axis: Dict[str, TelemetrySink]

    # --- device-scoped caches (multi-axis runs must pin these per axis) ---
    last_dev_params_by_axis: Dict[str, Dict[str, float]] = field(default_factory=dict)
    last_dev_estop_word_by_axis: Dict[str, int] = field(default_factory=dict)
    last_dev_param_edit_active_by_axis: Dict[str, bool] = field(default_factory=dict)
    last_dev_param_edit_group_by_axis: Dict[str, str] = field(default_factory=dict)

    # Raw PLC uplink payload caches (per axis). HiP may consume these directly.
    last_dev_plc_uplink_fields_by_axis: Dict[str, Dict[str, str]] = field(default_factory=dict)
    last_dev_plc_uplink_tail_by_axis: Dict[str, Dict[str, str]] = field(default_factory=dict)

    last_dev_param_commit_req_id_by_axis: Dict[str, str] = field(default_factory=dict)
    last_dev_param_commit_group_by_axis: Dict[str, str] = field(default_factory=dict)
    last_dev_param_commit_status_by_axis: Dict[str, str] = field(default_factory=dict)
    last_dev_param_commit_age_ticks_by_axis: Dict[str, int] = field(default_factory=dict)
    last_dev_param_commit_unmatched_by_axis: Dict[str, List[str]] = field(default_factory=dict)

    # --------------------
    # Command routing
    # --------------------
    def publish_command_frames(
        self,
        cmd_frame: CommandFrame,
        *,
        estop_reset_by_axis: Optional[Mapping[str, bool]] = None,
        param_ops_by_axis: Optional[Mapping[str, List[ParamOp]]] = None,
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
            echo_val = None
            try:
                echo_map = getattr(cmd_frame, "lifetick_echo", {}) or {}
                if isinstance(echo_map, dict):
                    echo_val = echo_map.get(axis_id)
            except Exception:
                echo_val = None
            lifetick_echo_axis = {axis_id: (int(echo_val) & 0xFFFF)} if echo_val is not None else {}

            frame_axis = CommandFrame(
                tick=cmd_frame.tick,
                t_s=cmd_frame.t_s,
                estop=cmd_frame.estop,
                fault=cmd_frame.fault,
                core_mode=cmd_frame.core_mode,
                axes={axis_id: sp},
                intent=bool(getattr(cmd_frame, "intent", True)),
                resync=bool(getattr(cmd_frame, "resync", False)),
                gui_not_halt=bool(getattr(cmd_frame, "gui_not_halt", False)),
                lifetick_echo=lifetick_echo_axis,
                estop_reset=bool(estop_reset_by_axis.get(axis_id, False)),
                param_ops=coerce_param_ops(param_ops_by_axis.get(axis_id, [])),
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
                    k = str(axes_keys[0])
                else:
                    k = None
                if not k:
                    continue

                self.last_dev_estop_word_by_axis[k] = int(getattr(s, "estop_status_word", 0))
                self.last_dev_params_by_axis[k] = dict(getattr(s, "params", {}) or {})
                self.last_dev_param_edit_active_by_axis[k] = bool(getattr(s, "param_edit_active", False))
                self.last_dev_param_edit_group_by_axis[k] = str(getattr(s, "param_edit_group", ""))

                # Raw PLC uplink payload (pre/post EOD). Keep as strings.
                self.last_dev_plc_uplink_fields_by_axis[k] = {str(a): str(b) for a, b in dict(getattr(s, "plc_uplink_fields", {}) or {}).items()}
                self.last_dev_plc_uplink_tail_by_axis[k] = {str(a): str(b) for a, b in dict(getattr(s, "plc_uplink_tail", {}) or {}).items()}

                self.last_dev_param_commit_req_id_by_axis[k] = str(getattr(s, "param_commit_req_id", ""))
                self.last_dev_param_commit_group_by_axis[k] = str(getattr(s, "param_commit_group", ""))
                self.last_dev_param_commit_status_by_axis[k] = str(getattr(s, "param_commit_status", "idle"))
                self.last_dev_param_commit_age_ticks_by_axis[k] = int(getattr(s, "param_commit_age_ticks", 0))
                self.last_dev_param_commit_unmatched_by_axis[k] = list(getattr(s, "param_commit_unmatched", []) or [])
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

        return TelemetrySnapshot(
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
            estop_status_word=int(self.last_dev_estop_word_by_axis.get(axis_id, int(getattr(snap, "estop_status_word", 0)))),
            param_edit_active=bool(self.last_dev_param_edit_active_by_axis.get(axis_id, bool(getattr(snap, "param_edit_active", False)))),
            param_edit_group=str(self.last_dev_param_edit_group_by_axis.get(axis_id, str(getattr(snap, "param_edit_group", "")))),
            params=dict(self.last_dev_params_by_axis.get(axis_id, dict(getattr(snap, "params", {})) or {})),
            plc_uplink_fields=dict(self.last_dev_plc_uplink_fields_by_axis.get(axis_id, dict(getattr(snap, "plc_uplink_fields", {})) or {})),
            plc_uplink_tail=dict(self.last_dev_plc_uplink_tail_by_axis.get(axis_id, dict(getattr(snap, "plc_uplink_tail", {})) or {})),
            core_acks=list(getattr(snap, "core_acks", [])),
            param_commit_req_id=str(self.last_dev_param_commit_req_id_by_axis.get(axis_id, str(getattr(snap, "param_commit_req_id", "")))),
            param_commit_group=str(self.last_dev_param_commit_group_by_axis.get(axis_id, str(getattr(snap, "param_commit_group", "")))),
            param_commit_status=str(self.last_dev_param_commit_status_by_axis.get(axis_id, str(getattr(snap, "param_commit_status", "idle")))),
            param_commit_age_ticks=int(self.last_dev_param_commit_age_ticks_by_axis.get(axis_id, int(getattr(snap, "param_commit_age_ticks", 0)))),
            param_commit_unmatched=list(self.last_dev_param_commit_unmatched_by_axis.get(axis_id, list(getattr(snap, "param_commit_unmatched", [])) or [])),
            joy=getattr(snap, "joy", JoyState()),
        )

    def publish_ui_snapshot(self, snap: TelemetrySnapshot) -> int:
        sent = 0
        for axis_id in self.axis_ids:
            tx = self.ui_telem_out_by_axis.get(axis_id)
            if tx is None:
                continue
            tx.publish_telemetry(self.slice_snapshot_for_axis(snap, axis_id))
            sent += 1
        return sent