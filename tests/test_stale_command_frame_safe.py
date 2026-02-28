from __future__ import annotations

from steuerung3d.core.intent_handler import apply_intent
from steuerung3d.core.intents import EnableAxis
from steuerung3d.core.state import MachineState


def test_stale_command_frame_is_ignored_when_claim_owner_differs() -> None:
    """If an axis is claimed by hip A, EnableAxis from hip B must not take effect.

    This protects us from stale or mis-routed command frames enabling motion.
    """

    st = MachineState()
    st.ensure_axis("Anton")

    # Simulate an existing claim by a different controller.
    st.set_axis_claim("Anton", "hip-A")

    apply_intent(st, EnableAxis(axis_id="Anton", enable=True, hip_id="hip-B"))

    # Enable must remain False (and ideally we didn't even create a command slot).
    if "Anton" in st.axis_cmd:
        assert st.axis_cmd["Anton"].enable is False
