from steuerung3d.apps.joy2intent.mapping import JoyBindings, JoyLimits, JoyRig, synthesize_intents
from steuerung3d.apps.joy2intent.state import JoyState
from steuerung3d.core.intents import JoyStateUpdate


class _Rc:
    def __init__(self, axes, pressed):
        self.axes=list(axes)
        self.pressed=set(pressed)


def test_multi_select_publishes_selected_axes() -> None:
    st = JoyState()
    bind = JoyBindings(axes={"manual_jog": 0, "soll_speed": 0}, buttons={"deadman": 5}, deadzone=0.05, expo=1.0, select_buttons=[0,1])
    rig = JoyRig(winches=["Anton", "Debby"])
    lim = JoyLimits(max_winch_mps=1.0, fine_scale=0.5)
    intents = synthesize_intents(st, _Rc([0.25], [5,0,1]), bind, rig, lim)
    js = next(i for i in intents if isinstance(i, JoyStateUpdate))
    assert set(js.selected_axes) == {"Anton", "Debby"}
    assert js.select_hip is True
