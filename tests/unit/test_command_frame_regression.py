from __future__ import annotations

import hashlib
import json
from typing import List

from steuerung3d.adapters.sim.axis_plant import SimAxisPlant
from steuerung3d.adapters.sim.device import SimDevice
from steuerung3d.common.timebase import Timebase
from steuerung3d.core.command_frame import CommandFrame
from steuerung3d.core.core_mode import CoreMode
from steuerung3d.core.engine import CoreEngine
from steuerung3d.core.intent_handler import apply_intent
from steuerung3d.core.intents import EnableAxis, JogAxis, RequestAxisLease, SetEstop
from steuerung3d.core.joy_state import JoyState
from steuerung3d.core.state import MachineState
from steuerung3d.protocol.codec import encode_command_frame
from steuerung3d.protocol.transport import InMemTransport


def _fingerprint(frames: List[CommandFrame]) -> str:
    # Build a stable representation for regression tests.
    # We intentionally ignore t_s to avoid float formatting drift.
    payloads = []
    for cf in frames:
        d = encode_command_frame(cf)
        d.pop("t_s", None)
        # Sort axes for stability
        axes = d.get("axes", {})
        if isinstance(axes, dict):
            d["axes"] = {k: axes[k] for k in sorted(axes.keys())}
        payloads.append(d)

    blob = json.dumps(payloads, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def test_command_frame_sequence_regression_hash():
    """Regression guard: command-frame sequence should not change silently.

    If this test fails and the change is intentional:
      1) update the baseline hash below
      2) add a short note in the PR/commit message explaining why
    """
    axis_ids = ["X", "Y"]

    transport = InMemTransport()
    tb = Timebase(dt_s=0.01)
    st = MachineState()
    for a in axis_ids:
        st.ensure_axis(a)
    st.core_mode = CoreMode.LIVE
    st.joy = JoyState(select_hip=True)

    frames: List[CommandFrame] = []

    sim = SimDevice(plant=SimAxisPlant())

    eng = CoreEngine(
        timebase=tb,
        state=st,
        drain_intents=transport.drain_intents,
        handle_intent=apply_intent,
        device_step=sim.step,
        on_command_frame=frames.append,
        on_snapshot=lambda _snap: None,
    )

    # Deterministic intent schedule
    hip_id = "hipA"
    for a in axis_ids:
        transport.publish_intent(RequestAxisLease(axis_id=a, hip_id=hip_id, req_id=f"lease-{a}"))
    eng.step_once()  # tick=1

    for a in axis_ids:
        transport.publish_intent(EnableAxis(axis_id=a, enable=True, hip_id=hip_id))  # tick=1

    transport.publish_intent(JogAxis(axis_id="X", vel=0.5, hip_id=hip_id))
    transport.publish_intent(JogAxis(axis_id="Y", vel=-0.25, hip_id=hip_id))

    eng.run_for_ticks(20)

    transport.publish_intent(SetEstop(estop=True))
    eng.run_for_ticks(5)

    assert frames, "expected command frames"
    got = _fingerprint(frames)

    # Baseline generated from current deterministic SIM behavior.
    expected = "0ef3620965a07a72c0edbf4c0184a06169cf3dbb1f2938e7ad77682272b75de9"  # updated: CommandFrame now carries amp reset pulses
    assert got == expected, f"command-frame regression hash changed: {got} != {expected}"
