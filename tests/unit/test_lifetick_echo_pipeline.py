from __future__ import annotations


from steuerung3d.core.intent_handler import apply_intent
from steuerung3d.core.intents import EchoLifeTick
from steuerung3d.core.executor import build_command_frame
from steuerung3d.core.state import MachineState


def test_echo_lifetick_intent_is_inserted_into_command_frame() -> None:
    st = MachineState()
    st.ensure_axis("Cecil")
    st.ensure_axis("Debby")

    # Simulate HiP echoing the latest device-side tick back to core.
    apply_intent(st, EchoLifeTick(axis_id="Cecil", value=12345, hip_id="hip-test"), now_tick=1)

    cmd_c = build_command_frame(st, "Cecil")
    cmd_d = build_command_frame(st, "Debby")

    assert cmd_c.lifetick_echo == 12345
    assert cmd_d.lifetick_echo == 0


def test_echo_lifetick_is_masked_to_16bit() -> None:
    st = MachineState()
    st.ensure_axis("Anton")

    apply_intent(st, EchoLifeTick(axis_id="Anton", value=70000, hip_id="hip-test"), now_tick=1)

    cmd = build_command_frame(st, "Anton")
    assert cmd.lifetick_echo == (70000 & 0xFFFF)
