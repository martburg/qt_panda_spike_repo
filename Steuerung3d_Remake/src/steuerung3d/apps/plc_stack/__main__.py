from __future__ import annotations

import time
from pathlib import Path

from steuerung3d.adapters.links.udp_link import UdpLink
from steuerung3d.adapters.plc.multi_plc_device import MultiPlcDevice
from steuerung3d.adapters.plc.plc_codec import PlcCodec
from steuerung3d.adapters.plc.plc_config import PlcWireSpec
from steuerung3d.adapters.plc.plc_endpoint import PlcEndpoint
from steuerung3d.adapters.plc.validate import validate_endpoints
from steuerung3d.common.timebase import Timebase
from steuerung3d.core.engine import CoreEngine
from steuerung3d.core.intent_handler import apply_intent
from steuerung3d.core.intents import ArmLiveMode, EnableAxis, JogAxis, SetEstop
from steuerung3d.core.state import MachineState
from steuerung3d.protocol.core_runner import CoreRunner
from steuerung3d.protocol.recording import JsonlRecorder, LoggedTransport
from steuerung3d.protocol.transport import InMemTransport


# TODO: replace this static list with a config file (TOML) once multi-axis is active.
# Mixed assignment is supported: each endpoint can own 1..N axes.
PLC_ENDPOINTS = [
    # name, target_host, target_port, bind_host, bind_port, axis_ids
    ("Anton", "172.16.17.1", 50001, "0.0.0.0", 51001, ["X"]),
    ("Burt",  "172.16.17.2", 50001, "0.0.0.0", 51002, ["Y"]),
    ("Cecil", "172.16.17.3", 50001, "0.0.0.0", 51003, ["Z"]),
    ("Debby", "172.16.17.4", 50001, "0.0.0.0", 51004, ["W"]),
]


def main() -> int:
    # --- internal transport (core <-> client in-process) ---
    raw = InMemTransport()
    rec = JsonlRecorder(Path("logs/session_plc.jsonl"))
    transport = LoggedTransport(raw, rec)

    # --- build PLC endpoints ---
    endpoints: list[PlcEndpoint] = []
    all_axes: list[str] = []

    for name, target_host, target_port, bind_host, bind_port, axis_ids in PLC_ENDPOINTS:
        all_axes.extend(axis_ids)

        spec = PlcWireSpec(axis_ids=list(axis_ids))
        codec = PlcCodec(spec=spec)
        link = UdpLink(bind=(bind_host, bind_port), target=(target_host, target_port))

        endpoints.append(
            PlcEndpoint(
                name=name,
                axis_ids=list(axis_ids),
                link=link,
                codec=codec,
            )
        )

    validate_endpoints(endpoints)
    device = MultiPlcDevice(endpoints=endpoints)

    # --- core ---
    tb = Timebase(dt_s=0.01)  # 100 Hz default
    st = MachineState()
    for a in all_axes:
        st.ensure_axis(a)

    eng = CoreEngine(
        timebase=tb,
        state=st,
        drain_intents=transport.drain_intents,
        handle_intent=apply_intent,
        device_step=device.step,
        on_snapshot=transport.publish_telemetry,
        on_command_frame=rec.record_command_frame,
    )

    runner = CoreRunner(engine=eng, realtime=True)
    runner.start()

    # --- demo behavior ---
    transport.publish_intent(ArmLiveMode())
    for a in all_axes:
        transport.publish_intent(EnableAxis(axis_id=a, enable=True))

    # Jog the first axis
    transport.publish_intent(JogAxis(axis_id=all_axes[0], vel=0.6))

    t0 = time.time()
    last_print = 0

    try:
        while True:
            snaps = transport.drain_telemetry(limit=500)
            for snap in snaps:
                if snap.tick - last_print >= 50:
                    last_print = snap.tick
                    ax0 = snap.axes[all_axes[0]]
                    print(
                        f"tick={snap.tick:5d} t={snap.t_s:6.2f}s mode={snap.mode} "
                        f"estop={snap.estop} fault={snap.fault} "
                        f"{all_axes[0]}(en={ax0.enabled}, vel={ax0.vel:5.2f}, pos={ax0.pos:8.3f}) "
                        f"rx_ticks={device.last_rx_tick_by_endpoint}"
                    )

            if 2.5 < (time.time() - t0) < 2.55:
                transport.publish_intent(SetEstop(estop=True))

            if (time.time() - t0) > 6.0:
                break

            time.sleep(0.01)

    finally:
        runner.stop()
        runner.join(timeout=1.0)
        for ep in endpoints:
            ep.link.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
