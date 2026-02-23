"""Regression test: livetick echo pipeline (DenSi -> Core -> HiP -> Core -> DenSi).

This test is intentionally *in-memory* (no UDP, no Qt). It validates the core
contract used by the live tick echo feature:

1) Device telemetry provides a 16-bit device tick (ms-ish) via AxisTelemetry.device_tick.
2) HiP mirrors the last seen device tick using EchoLifeTick intents.
3) Core forwards the echoed value back to devices via CommandFrame.lifetick_echo.
4) The device-side staleness is computed as (tx - rx) & 0xFFFF.

We only regression-guard the deterministic pieces (2) and (3), and we validate
the staleness math (4) including WORD wrap.
"""

from __future__ import annotations

from steuerung3d.core.state import MachineState
from steuerung3d.core.telemetry import TelemetrySnapshot, AxisTelemetry, apply_measured_snapshot
from steuerung3d.core.intents import EchoLifeTick
from steuerung3d.core.intent_handler import apply_intent
from steuerung3d.core.executor import build_command_frame


def _snap_for_device_tick(axis_id: str, *, tick: int, t_s: float, device_tick: int) -> TelemetrySnapshot:
    return TelemetrySnapshot(
        tick=tick,
        t_s=t_s,
        core_mode="LIVE",
        estop=False,
        fault=False,
        axes={axis_id: AxisTelemetry(pos=0.0, vel=0.0, enabled=True, fault=False, device_tick=device_tick & 0xFFFF)},
        rig_mode="RigMode.DISCOVERY",
        densis={},
        estop_status_word=0,
        param_edit_active=False,
        param_edit_group="",
        params={},
        core_acks=[],
        param_commit_req_id="",
        param_commit_group="",
        param_commit_status="idle",
        param_commit_age_ticks=0,
        param_commit_unmatched=[],
    )


def test_livetick_echo_roundtrip_and_diff_math() -> None:
    axis = "Anton"
    st = MachineState()
    st.ensure_axis(axis)
    st.ensure_axis_cmd(axis)

    # Simulated DenSi tick counter: increases by 10ms per cycle.
    inc = 10
    tx = 1000
    rx = 0  # what DenSi has currently received back from Core/HiP

    for i in range(6):
        snap = _snap_for_device_tick(axis, tick=i, t_s=i * 0.01, device_tick=tx)
        apply_measured_snapshot(st, snap)

        # HiP mirrors what it *just* saw (device_tick) back to core.
        apply_intent(st, EchoLifeTick(axis_id=axis, value=tx & 0xFFFF, hip_id="hip-test"))

        cmd = build_command_frame(st)
        assert cmd.lifetick_echo.get(axis) == (tx & 0xFFFF)

        # DenSi computes staleness for *this* cycle using the echo received
        # from the previous cycle (pipeline delay). After the first warmup cycle,
        # it should stabilize to the increment.
        diff = (tx - (rx & 0xFFFF)) & 0xFFFF
        if i >= 1:
            assert diff == inc

        # Prepare next cycle: echo becomes the new rx, and device tick advances.
        rx = cmd.lifetick_echo.get(axis, 0)
        tx = (tx + inc) & 0xFFFF


def test_livetick_diff_wraps_as_word() -> None:
    # WORD wrap behavior is essential (matches legacy PLC/Beckhoff semantics).
    tx = 0xFFFE
    rx = 0x0005
    diff = (tx - rx) & 0xFFFF
    assert diff == 0xFFF9
