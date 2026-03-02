from __future__ import annotations

import argparse
import socket
from dataclasses import dataclass
from typing import Dict, Tuple

from steuerung3d.adapters.plc.line_codec import PlcLineCodec, parse_bool, parse_float, parse_int


@dataclass
class AxisSim:
    enabled: bool = False
    vel: float = 0.0
    pos: float = 0.0
    fault: int = 0

    # simple limits
    max_vel: float = 5.0
    max_acc: float = 5.0

    def step_towards(self, *, enable: bool, vel_sp: float, dt: float) -> None:
        self.enabled = bool(enable)
        if not self.enabled:
            self.vel = 0.0
            return

        # clamp
        if vel_sp > self.max_vel:
            vel_sp = self.max_vel
        elif vel_sp < -self.max_vel:
            vel_sp = -self.max_vel

        dv = vel_sp - self.vel
        dv_max = self.max_acc * dt
        if dv > dv_max:
            dv = dv_max
        elif dv < -dv_max:
            dv = -dv_max

        self.vel += dv
        self.pos += self.vel * dt


def _iter_lines(payload: bytes) -> Tuple[str, ...]:
    # Support either '\n' separated or single-line packets.
    txt = payload.decode("utf-8", errors="replace")
    lines = [ln.strip() for ln in txt.replace("\r", "\n").split("\n")]
    return tuple(ln for ln in lines if ln)


def run_server(host: str, port: int, dt_s: float, verbose: bool = False) -> int:
    codec = PlcLineCodec()
    axes: Dict[str, AxisSim] = {}

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((host, port))
    sock.settimeout(0.25)

    if verbose:
        print(f"PLCsim listening on udp://{host}:{port} dt={dt_s}s")

    last_tick = 0

    while True:
        try:
            payload, addr = sock.recvfrom(65535)
        except socket.timeout:
            # idle loop; nothing to do
            continue
        except KeyboardInterrupt:
            return 0

        resp_lines = []
        for line in _iter_lines(payload):
            rx = codec.decode_rx(line)

            tick = parse_int(rx.get("tick", "0"), default=last_tick)
            axis = rx.get("axis", "X")
            enable = parse_bool(rx.get("enable", "0"))
            vel_sp = parse_float(rx.get("vel", "0"))

            sim = axes.setdefault(axis, AxisSim())
            sim.step_towards(enable=enable, vel_sp=vel_sp, dt=dt_s)

            last_tick = tick

            tx_map = {
                "tick": tick,
                "axis": axis,
                "enabled": 1 if sim.enabled else 0,
                "vel": f"{sim.vel:.6f}",
                "pos": f"{sim.pos:.6f}",
                "fault": sim.fault,
            }
            resp_lines.append(codec.encode_tx(tx_map))

            if verbose:
                print(f"rx {addr} : {line}")
                print(f"tx {addr} : {resp_lines[-1]}")

        if resp_lines:
            sock.sendto(("\n".join(resp_lines)).encode("utf-8"), addr)


def main() -> int:
    ap = argparse.ArgumentParser(description="UDP PLC simulator (semicolon-separated lines)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=55001)
    ap.add_argument("--dt", type=float, default=0.01, help="tick time step (s)")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    return run_server(args.host, args.port, dt_s=args.dt, verbose=args.verbose)


if __name__ == "__main__":
    raise SystemExit(main())
