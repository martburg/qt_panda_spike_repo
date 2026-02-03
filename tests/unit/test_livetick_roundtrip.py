from __future__ import annotations

from steuerung3d.adapters.sim.axis_plant import SimAxisPlant
from steuerung3d.core.executor import build_command_frame
from steuerung3d.core.intent_handler import apply_intent
from steuerung3d.core.intents import EchoLifeTick
from steuerung3d.core.state import MachineState
from steuerung3d.core.telemetry import TelemetrySnapshot
from steuerung3d.util.tick import tick_delta_16


def test_livetick_roundtrip_densi_core_hip_core_densi_diff_is_step_ms() -> None:
    st = MachineState()
    axis_id = "Anton"
    st.ensure_axis(axis_id)
    st.ensure_axis_cmd(axis_id)

    plant = SimAxisPlant()
    dt = 0.010
    step_ms = max(1, int(dt * 1000.0))

    # Tick 0: core sends empty echo map
    cmd = build_command_frame(st)

    prev_tx = None

    for i in range(6):
        # --- device step: updates tx and (if present) rx from cmd.lifetick_echo ---
        plant.step(st, cmd, dt)

        tx = int(st.axes[axis_id].meta.get("device_tick", 0)) & 0xFFFF
        rx = int(st.axes[axis_id].meta.get("lifetick_rx", 0)) & 0xFFFF

        # --- device -> core telemetry snapshot ---
        snap = TelemetrySnapshot.from_state(st)

        # --- hip echoes current tx back to core ---
        apply_intent(st, EchoLifeTick(axis_id=axis_id, value=snap.axes[axis_id].device_tick, hip_id="hip-test"))

        # --- next core frame (contains echo) ---
        st.tick += 1
        st.t_s += dt
        cmd = build_command_frame(st)

        # After the first echo has had a chance to come back (i >= 1),
        # rx should equal the previous tx, and diff should equal step_ms.
        if i >= 1 and prev_tx is not None:
            assert rx == prev_tx
            assert tick_delta_16(tx, rx) == step_ms

        prev_tx = tx
