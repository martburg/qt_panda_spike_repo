from __future__ import annotations

from pathlib import Path

import pytest

from steuerung3d.config.plc_stack_config import load_plc_stack_config
from steuerung3d.adapters.sim.axis_plant import SimAxisPlant
from steuerung3d.adapters.sim.device import SimDevice
from steuerung3d.core.intents import ArmLiveMode, EnableAxis, JogAxis, SetEstop

from steuerung3d.apps.plc_stack.builder import build_core


def _write(path: Path, s: str) -> None:
    path.write_text(s, encoding="utf-8")


def test_plc_stack_toml_parses_multiple_endpoints(tmp_path: Path) -> None:
    toml_path = tmp_path / "plc_stack.toml"
    _write(
        toml_path,
        """\
[app]
dt_s = 0.02
realtime = false
log_path = "logs/test.jsonl"

[[plc_endpoints]]
name = "Anton"
bind_host = "0.0.0.0"
bind_port = 51001
target_host = "172.16.17.1"
target_port = 50001
axis_ids = ["X"]

[[plc_endpoints]]
name = "Burt"
bind_host = "0.0.0.0"
bind_port = 51002
target_host = "172.16.17.2"
target_port = 50001
axis_ids = ["Y", "Z"]
""",
    )

    cfg = load_plc_stack_config(toml_path)

    assert cfg.app.dt_s == 0.02
    assert cfg.app.realtime is False
    assert cfg.app.log_path.endswith("logs/test.jsonl")

    assert len(cfg.plc_endpoints) == 2
    assert cfg.plc_endpoints[0].name == "Anton"
    assert cfg.plc_endpoints[0].axis_ids == ["X"]
    assert cfg.plc_endpoints[1].name == "Burt"
    assert cfg.plc_endpoints[1].axis_ids == ["Y", "Z"]


def test_plc_stack_toml_rejects_duplicate_axis_ownership(tmp_path: Path) -> None:
    toml_path = tmp_path / "plc_stack.toml"
    _write(
        toml_path,
        """\
[app]
dt_s = 0.01

[[plc_endpoints]]
name = "Anton"
bind_host = "0.0.0.0"
bind_port = 51001
target_host = "172.16.17.1"
target_port = 50001
axis_ids = ["X", "Y"]

[[plc_endpoints]]
name = "Burt"
bind_host = "0.0.0.0"
bind_port = 51002
target_host = "172.16.17.2"
target_port = 50001
axis_ids = ["Y"]
""",
    )

    with pytest.raises(ValueError, match=r"Axis 'Y' is owned by both"):
        load_plc_stack_config(toml_path)


def test_engine_multi_axis_uses_axes_from_toml_via_plc_stack_builder(tmp_path: Path) -> None:
    """SIM-only: prove that TOML endpoint axis_ids become real axes using the *real* plc_stack builder."""
    toml_path = tmp_path / "plc_stack.toml"
    _write(
        toml_path,
        """\
[app]
dt_s = 0.01
realtime = false

[[plc_endpoints]]
name = "Anton"
bind_host = "0.0.0.0"
bind_port = 51001
target_host = "127.0.0.1"
target_port = 50001
axis_ids = ["X"]

[[plc_endpoints]]
name = "Burt"
bind_host = "0.0.0.0"
bind_port = 51002
target_host = "127.0.0.1"
target_port = 50002
axis_ids = ["Y"]
""",
    )

    cfg = load_plc_stack_config(toml_path)

    sim = SimDevice(plant=SimAxisPlant())

    rt = build_core(cfg, device_step=sim.step, enable_logging=False)
    tr = rt.transport
    eng = rt.engine
    st = rt.state

    # Activate + enable both axes and jog them differently.
    tr.publish_intent(ArmLiveMode())
    eng.step_once()

    tr.publish_intent(EnableAxis(axis_id="X", enable=True))
    tr.publish_intent(EnableAxis(axis_id="Y", enable=True))
    tr.publish_intent(JogAxis(axis_id="X", vel=0.4))
    tr.publish_intent(JogAxis(axis_id="Y", vel=-0.1))

    for _ in range(50):
        eng.step_once()

    pos_x = st.axes["X"].pos
    pos_y = st.axes["Y"].pos

    # ESTOP should stop motion; positions should hold.
    tr.publish_intent(SetEstop(estop=True))
    for _ in range(10):
        eng.step_once()

    assert st.axes["X"].pos == pos_x
    assert st.axes["Y"].pos == pos_y

    # Very weak sanity: motion happened before estop.
    assert abs(pos_x) > 0.0
    assert abs(pos_y) > 0.0
