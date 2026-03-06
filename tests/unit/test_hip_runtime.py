from __future__ import annotations

import logging

from steuerung3d.apps.yellow.engines.hip.engine import HipEngine, HipUiInputs
from steuerung3d.apps.yellow.runtimes.hip_runtime import HipRuntime, HipRuntimeInputs
from steuerung3d.core.intents import ClaimAxis
from steuerung3d.core.telemetry import AxisTelemetry, DensiTelemetry, TelemetrySnapshot
from steuerung3d.util.heartbeat import ChangeTracker, Heartbeat


def _runtime() -> HipRuntime:
    engine = HipEngine(hip_id="hip-test")
    hb = Heartbeat("hi_p", interval_s=1.0)
    ch = ChangeTracker()
    return HipRuntime(
        engine=engine,
        hb=hb,
        ch=ch,
        status=None,
        stale_after_ms=5,
        log=logging.getLogger("test.hip_runtime"),
        hip_id="hip-test",
        shadow_mode="old",
    )


def _snap(axis_id: str = "A", device_tick: int = 10) -> TelemetrySnapshot:
    return TelemetrySnapshot(
        tick=1,
        t_s=0.0,
        core_mode="IDLE",
        estop=False,
        fault=False,
        axes={
            axis_id: AxisTelemetry(
                pos=0.0,
                vel=0.0,
                enabled=True,
                fault=False,
                device_tick=device_tick & 0xFFFF,
            )
        },
        densis={
            axis_id: DensiTelemetry(
                device_id=axis_id,
                online=True,
                claimed_by_hip="",
                participating=False,
                anchor_xyz=None,
                last_seen_age_ticks=0,
            )
        },
    )


def test_hip_runtime_sets_startup_on_stale_gap() -> None:
    rt = _runtime()
    ui = HipUiInputs(
        axis_selected="",
        axis_selection_changed=False,
        estop_reset_clicked=False,
        resync_clicked=False,
        main_reset_clicked=False,
        guider_reset_clicked=False,
        param_actions=[],
        param_values={},
    )

    res = rt.tick(inputs=HipRuntimeInputs(snaps=[_snap()], now_ns=10_000_000, ui=ui))
    assert res.view_model is not None
    assert res.apply_startup_state is False

    res2 = rt.tick(inputs=HipRuntimeInputs(snaps=[], now_ns=16_000_000, ui=ui))
    assert res2.apply_startup_state is True


def test_hip_runtime_emits_claim_axis_intent() -> None:
    rt = _runtime()
    ui = HipUiInputs(
        axis_selected="A",
        axis_selection_changed=True,
        estop_reset_clicked=False,
        resync_clicked=False,
        main_reset_clicked=False,
        guider_reset_clicked=False,
        param_actions=[],
        param_values={},
    )

    res = rt.tick(inputs=HipRuntimeInputs(snaps=[_snap("A")], now_ns=10_000_000, ui=ui))
    assert any(isinstance(intent, ClaimAxis) for intent in res.intents)


def test_hip_runtime_attach_combo_hides_targets_claimed_by_other_hips() -> None:
    rt = _runtime()
    snap = TelemetrySnapshot(
        tick=1,
        t_s=0.0,
        core_mode="IDLE",
        estop=False,
        fault=False,
        axes={
            "Anton": AxisTelemetry(pos=0.0, vel=0.0, enabled=True, fault=False),
            "Debby": AxisTelemetry(pos=0.0, vel=0.0, enabled=True, fault=False),
            "Cecil": AxisTelemetry(pos=0.0, vel=0.0, enabled=True, fault=False),
        },
        densis={
            "Anton": DensiTelemetry(
                device_id="Anton", online=True, claimed_by_hip="", last_seen_age_ticks=0
            ),
            "Debby": DensiTelemetry(
                device_id="Debby", online=True, claimed_by_hip="other-hip", last_seen_age_ticks=0
            ),
            "Cecil": DensiTelemetry(
                device_id="Cecil", online=True, claimed_by_hip="hip-test", last_seen_age_ticks=0
            ),
        },
    )
    ui = HipUiInputs(
        axis_selected="",
        axis_selection_changed=False,
        estop_reset_clicked=False,
        resync_clicked=False,
        main_reset_clicked=False,
        guider_reset_clicked=False,
        param_actions=[],
        param_values={},
    )

    res = rt.tick(inputs=HipRuntimeInputs(snaps=[snap], now_ns=10_000_000, ui=ui))

    assert res.view_model is not None
    assert res.view_model.attach_combo is not None
    assert res.view_model.attach_combo.items == ["NotAttached", "Anton", "Cecil"]


def test_hip_runtime_uses_axis_scoped_fields_for_selected_axis_in_fanout_snapshot() -> None:
    rt = _runtime()
    snap = TelemetrySnapshot(
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
                device_id="Anton", online=True, claimed_by_hip="hip-test", last_seen_age_ticks=0
            ),
            "Debby": DensiTelemetry(
                device_id="Debby", online=True, claimed_by_hip="", last_seen_age_ticks=0
            ),
        },
        params={"VelMax": 9.9},
        plc_uplink_fields={"Axis": "GLOBAL"},
        axis_params={"Anton": {"VelMax": 1.25}, "Debby": {"VelMax": 2.5}},
        axis_plc_uplink_fields={"Anton": {"Axis": "Anton"}, "Debby": {"Axis": "Debby"}},
    )
    ui = HipUiInputs(
        axis_selected="Anton",
        axis_selection_changed=True,
        estop_reset_clicked=False,
        resync_clicked=False,
        main_reset_clicked=False,
        guider_reset_clicked=False,
        param_actions=[],
        param_values={},
    )

    res = rt.tick(inputs=HipRuntimeInputs(snaps=[snap], now_ns=10_000_000, ui=ui))
    assert res.view_model is not None
    assert res.view_model.param_values.get("VelMax") == 1.25
