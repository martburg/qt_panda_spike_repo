"""Manual smoke test helper (no Qt).

Runs a tiny in-process scenario:
  - creates a MachineState
  - simulates telemetry (axis discovery)
  - claims an axis
  - attempts enable/jog from different hip_ids

Usage:
  python tools/smoke_autoclaim.py
"""

from steuerung3d.core.intent_handler import apply_intent
from steuerung3d.core.intents import ClaimAxis, EnableAxis, JogAxis
from steuerung3d.core.state import MachineState
from steuerung3d.core.telemetry import TelemetrySnapshot


def main():
    st = MachineState()

    # Pretend discovery happened
    st.ensure_axis("Anton").pos = 1.0
    st.ensure_axis("Debby").pos = 2.0

    snap = TelemetrySnapshot.from_state(st)
    print("Discovered axes:", ", ".join(sorted(snap.axes.keys())))

    # Claim Anton
    apply_intent(st, ClaimAxis(axis_id="Anton", hip_id="hipA", req_id="c1"))
    print("Claims:", st.axis_claims, "acks:", st.core_acks)

    # hipB tries to enable/jog
    apply_intent(st, EnableAxis(axis_id="Anton", enable=True, hip_id="hipB"))
    apply_intent(st, JogAxis(axis_id="Anton", vel=0.5, hip_id="hipB"))
    print("After hipB enable/jog, axis_cmd:", st.axis_cmd)

    # hipA enables/jogs
    apply_intent(st, EnableAxis(axis_id="Anton", enable=True, hip_id="hipA"))
    apply_intent(st, JogAxis(axis_id="Anton", vel=0.5, hip_id="hipA"))
    print("After hipA enable/jog, axis_cmd:", st.axis_cmd)

    print("OK.")


if __name__ == "__main__":
    main()
