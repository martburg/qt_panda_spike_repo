from __future__ import annotations

from steuerung3d.apps.yellow.engines.hip.engine import HipEngine, HipUiInputs
from steuerung3d.apps.yellow.engines.hip.types import HipStepInputs
from steuerung3d.core.telemetry import AxisTelemetry, DensiTelemetry, TelemetrySnapshot


def _ui(axis_selected: str = "", changed: bool = False) -> HipUiInputs:
    return HipUiInputs(
        axis_selected=axis_selected,
        axis_selection_changed=changed,
        estop_reset_clicked=False,
        resync_clicked=False,
        main_reset_clicked=False,
        guider_reset_clicked=False,
        param_actions=[],
        param_values={},
    )


def _snap() -> TelemetrySnapshot:
    return TelemetrySnapshot(
        tick=1,
        t_s=0.0,
        core_mode="IDLE",
        estop=False,
        fault=False,
        axes={
            "Anton": AxisTelemetry(pos=1.0, vel=0.1, enabled=True, fault=False),
            "Debby": AxisTelemetry(pos=2.0, vel=0.2, enabled=True, fault=False),
        },
        densis={
            "Anton": DensiTelemetry(
                device_id="Anton", online=True, claimed_by_hip="", last_seen_age_ticks=0
            ),
            "Debby": DensiTelemetry(
                device_id="Debby", online=True, claimed_by_hip="", last_seen_age_ticks=0
            ),
        },
        params={"VelMax": 9.9},
        plc_uplink_fields={"Axis": "Anton"},
        axis_params={"Anton": {"VelMax": 1.1}, "Debby": {"VelMax": 2.2}},
        axis_plc_uplink_fields={"Anton": {"Axis": "Anton"}, "Debby": {"Axis": "Debby"}},
        axis_estop_status_word={"Anton": 11, "Debby": 22},
    )


def test_hip_presentation_blanks_device_surface_when_unattached() -> None:
    eng = HipEngine(hip_id="hip-test")
    res = eng.step(
        HipStepInputs(
            snap=_snap(),
            hip_id="hip-test",
            last_rx_ns=0,
            now_ns=0,
            stale_after_ms=500,
            fixed_axis="",
            lock_axis_combo=False,
            last_mode="IDLE",
            last_estate="IDLE",
            ui=_ui(),
            core_acks=[],
            joy=None,
        )
    )
    assert res.presentation is not None
    assert res.presentation.param_values == {}


def test_hip_presentation_uses_attached_axis_surface() -> None:
    eng = HipEngine(hip_id="hip-test")
    res = eng.step(
        HipStepInputs(
            snap=_snap(),
            hip_id="hip-test",
            last_rx_ns=0,
            now_ns=0,
            stale_after_ms=500,
            fixed_axis="Debby",
            lock_axis_combo=False,
            last_mode="IDLE",
            last_estate="IDLE",
            ui=_ui(),
            core_acks=[],
            joy=None,
        )
    )
    assert res.presentation is not None
    assert res.presentation.param_values.get("VelMax") == 2.2


def test_hip_fixed_axis_auto_attaches_and_claims() -> None:
    eng = HipEngine(hip_id="hip-test")
    res = eng.step(
        HipStepInputs(
            snap=_snap(),
            hip_id="hip-test",
            last_rx_ns=0,
            now_ns=0,
            stale_after_ms=500,
            fixed_axis="Anton",
            lock_axis_combo=True,
            last_mode="IDLE",
            last_estate="IDLE",
            ui=_ui(),
            core_acks=[],
            joy=None,
        )
    )
    assert res.presentation is not None
    assert res.presentation.attach_combo is not None
    assert res.presentation.attach_combo.current == "Anton"
    assert res.presentation.attach_combo.enabled is False
    assert any(getattr(intent, "axis_id", "") == "Anton" for intent in res.intents)
