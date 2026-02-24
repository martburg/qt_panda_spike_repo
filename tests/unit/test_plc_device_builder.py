from __future__ import annotations

from pathlib import Path

from steuerung3d.apps.plc_stack.builder import build_plc_device
from steuerung3d.config.plc_stack_config import load_plc_stack_config


class FakeUdpLink:
    """Socket-free stand-in for UdpLink (for unit tests)."""

    def __init__(self, *, bind: tuple[str, int], target: tuple[str, int]):
        self.bind = bind
        self.target = target
        self.closed = False

    def close(self) -> None:
        self.closed = True


class FakeCodec:
    def __init__(self, *, spec, axis_id: str):
         self.spec = spec
    self.axis_id = axis_id


def test_build_plc_device_constructs_endpoints_without_opening_sockets(tmp_path: Path) -> None:
    toml_path = tmp_path / "plc_stack.toml"
    toml_path.write_text(
        """\
[app]
dt_s = 0.01
realtime = false

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
        encoding="utf-8",
    )

    cfg = load_plc_stack_config(toml_path)

    device, endpoints = build_plc_device(
        cfg,
        link_factory=lambda *, bind, target: FakeUdpLink(bind=bind, target=target),
        codec_factory=lambda *, spec, axis_id: FakeCodec(spec=spec, axis_id=axis_id),    )

    assert len(endpoints) == 2
    assert endpoints[0].name == "Anton"
    assert endpoints[0].axis_ids == ["X"]
    assert endpoints[0].link.bind == ("0.0.0.0", 51001)
    assert endpoints[0].link.target == ("172.16.17.1", 50001)
    assert endpoints[0].codec.axis_id == "Anton"

    assert endpoints[1].name == "Burt"
    assert endpoints[1].axis_ids == ["Y", "Z"]
    assert endpoints[1].link.bind == ("0.0.0.0", 51002)
    assert endpoints[1].link.target == ("172.16.17.2", 50001)
    assert endpoints[1].codec.axis_id == "Burt"

    # MultiPlcDevice should expose endpoint names (smoke check)
    assert hasattr(device, "endpoints")
    assert [ep.name for ep in device.endpoints] == ["Anton", "Burt"]
