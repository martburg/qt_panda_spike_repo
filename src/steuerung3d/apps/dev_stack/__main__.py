from __future__ import annotations

import argparse
import socket
import time
import tomllib
from pathlib import Path

from steuerung3d.adapters.plc.udp_device import UdpPlcDevice
from steuerung3d.adapters.plc_twincat_legacy.config import load_plc_twincat_legacy_fleet_from_toml
from steuerung3d.adapters.sim.axis_plant import SimAxisPlant
from steuerung3d.adapters.sim.device import SimDevice
from steuerung3d.common.timebase import Timebase
from steuerung3d.core.engine import CoreEngine
from steuerung3d.core.intent_handler import apply_intent
from steuerung3d.core.intents import EnableAxis, JogAxis, SetEstop
from steuerung3d.core.state import MachineState
from steuerung3d.protocol.core_runner import CoreRunner
from steuerung3d.protocol.recording import JsonlRecorder, LoggedTransport
from steuerung3d.protocol.transport import InMemTransport


def _can_bind_ip(ip: str) -> bool:
    """Return True if this host can bind a UDP socket to (ip, 0)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.bind((ip, 0))
        finally:
            s.close()
        return True
    except OSError as e:
        # Windows: WSAEADDRNOTAVAIL (cannot assign requested address)
        if getattr(e, "winerror", None) == 10049:
            return False
        return False


def _load_device_from_config(config_path: Path, plant: SimAxisPlant):
    cfg = tomllib.loads(config_path.read_text(encoding="utf-8"))
    device_cfg = cfg.get("device", {})
    kind = device_cfg.get("kind", "sim")

    if kind == "plc_twincat_legacy_fleet":
        fleet_cfg = device_cfg.get("plc_twincat_legacy_fleet", {})
        defaults = fleet_cfg.get("defaults", {})
        controller_ip = str(defaults.get("controller_ip", "0.0.0.0"))

        # If the controller_ip isn't present on this host (common on laptops/off-network),
        # fall back to loopback UDP PLC simulators.
        if not _can_bind_ip(controller_ip):
            print(
                f"[dev_stack] controller_ip={controller_ip} not present on this host -> "
                f"using UDP SIM fallback for plc_twincat_legacy_fleet"
            )
            from steuerung3d.adapters.plc_twincat_legacy.udp_sim import (
                build_udp_sim_fleet_from_toml,
            )

            # Returns an object with .step(...) and .close()
            return build_udp_sim_fleet_from_toml(config_path, dt_s=0.01)

        return load_plc_twincat_legacy_fleet_from_toml(config_path)

    if kind == "udp_plc_toy":
        toy = device_cfg.get("udp_plc_toy", {})
        remote_ip = str(toy.get("remote_ip", "127.0.0.1"))
        remote_port = int(toy.get("remote_port", 55001))
        return UdpPlcDevice(remote=(remote_ip, remote_port))

    # default: sim
    return SimDevice(plant)


def _axis_ids_from_config(config_path: Path) -> list[str]:
    """Extract axis ids from plc_twincat_legacy_fleet config (fallback to ['X'])."""
    try:
        cfg = tomllib.loads(config_path.read_text(encoding="utf-8"))
        fleet_axes = cfg.get("device", {}).get("plc_twincat_legacy_fleet", {}).get("axes", [])
        axis_ids = [str(a.get("axis_id")) for a in fleet_axes if a.get("axis_id")]
        return axis_ids if axis_ids else ["X"]
    except Exception:
        return ["X"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    config_path = Path(args.config)

    raw = InMemTransport()
    rec = JsonlRecorder(Path("logs/session.jsonl"))
    transport = LoggedTransport(raw, rec)

    tb = Timebase(dt_s=0.01)  # 100 Hz
    st = MachineState()

    plant = SimAxisPlant()
    device = _load_device_from_config(config_path, plant)

    axis_ids = _axis_ids_from_config(config_path)


    # Ensure all axes exist so snapshots have stable keys
    for aid in axis_ids:
        st.ensure_axis(aid)

    def on_step(state: MachineState, dt: float) -> None:
        # SIM plant stepping only truly matters for SimDevice; harmless otherwise
        plant.step(state, dt)

    def on_snapshot(snap) -> None:
        transport.publish_telemetry(snap)

    eng = CoreEngine(
        timebase=tb,
        state=st,
        drain_intents=transport.drain_intents,
        handle_intent=apply_intent,
        device_step=device.step,
        on_snapshot=on_snapshot,
    )

    runner = CoreRunner(engine=eng, realtime=True)
    runner.start()

    # ---- Client behavior (v0.1): send some intents, print telemetry ----
    # Enable + jog ALL axes (so you see Burt/Cecil/Debby too)
    for aid in axis_ids:
        transport.publish_intent(EnableAxis(axis_id=aid, enable=True))
        transport.publish_intent(JogAxis(axis_id=aid, vel=0.6))

    t0 = time.time()
    last_print = 0

    try:
        while True:
            snaps = transport.drain_telemetry(limit=500)
            for snap in snaps:
                if snap.tick - last_print >= 50:  # every 0.5s at 100 Hz
                    last_print = snap.tick

                    parts: list[str] = []
                    for aid in axis_ids:
                        if aid in snap.axes:
                            a = snap.axes[aid]
                            parts.append(f"{aid}(en={a.enabled}, vel={a.vel:5.2f}, pos={a.pos:8.3f})")

                    print(
                        f"tick={snap.tick:5d} t={snap.t_s:6.2f}s core_mode={snap.core_mode} estop={snap.estop} "
                        + " ".join(parts)
                    )

            # demonstrate estop after ~2.5s wall time
            if 2.5 < (time.time() - t0) < 2.55:
                transport.publish_intent(SetEstop(estop=True))

            # stop after ~6s
            if (time.time() - t0) > 6.0:
                break

            time.sleep(0.01)

    finally:
        runner.stop()
        runner.join(timeout=1.0)

        close = getattr(device, "close", None)
        if callable(close):
            close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
