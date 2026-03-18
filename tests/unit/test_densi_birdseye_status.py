from __future__ import annotations

from types import SimpleNamespace
from typing import cast

from steuerung3d.apps.yellow.runtimes.densi_runtime_status import build_densi_status_payload
from steuerung3d.apps.yellow.runtimes.densi_runtime_types import DensiRuntimeStatusPayloadLike


class _Axis:
    def __init__(self) -> None:
        self.vel = 0.25
        self.pos = 12.5
        self.meta = {"plc_lifetick_age_ticks": 7}


def test_densi_birdseye_includes_debug_payload() -> None:
    runtime = SimpleNamespace(
        _last_cmd_ns=1,
        _stale_after_ms=500,
        _seen_first_cmd=True,
        _last_estop=False,
        _last_fault=False,
        _axis_ids=["Anton"],
        _last_mode="LIVE",
        _last_cmd=SimpleNamespace(
            core_mode="LIVE",
            intent=True,
            axes={"Anton": SimpleNamespace(enable=True, vel=0.5)},
        ),
        engine=SimpleNamespace(
            drive_ready=True,
            state=SimpleNamespace(
                estop=False,
                fault=False,
                tick=42,
                axes={"Anton": _Axis()},
            ),
        ),
    )

    payload = build_densi_status_payload(
        runtime=cast(DensiRuntimeStatusPayloadLike, runtime), now_ns=2_000_000
    )

    assert payload.fields["axis"] == "Anton"
    assert payload.fields["cmd_enable"] is True
    debug = cast(dict[str, object], payload.fields.get("debug"))
    assert isinstance(debug, dict)
    assert debug.get("axis_selected") == "Anton"
    assert debug.get("cmd_vel") == 0.5
    assert debug.get("vel_applied") == 0.25
    assert debug.get("lifetick_age_ticks") == 7
