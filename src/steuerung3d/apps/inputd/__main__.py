from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path
from typing import List, Optional

from steuerung3d.core.status import StatusEmitter
from steuerung3d.protocol.raw_controls import RawControls
from steuerung3d.protocol.udp_channels import UdpRawControlsOut
from steuerung3d.util.app_bootstrap import bootstrap_logging
from steuerung3d.util.heartbeat import ChangeTracker, Heartbeat

from .config import InputdConfig, load_inputd_config
from .pygame_backend import PygameJoystick, clamp, deadzone_expo

log = logging.getLogger("inputd")


def _postprocess_axes(
    axes: List[float],
    *,
    invert_axes: dict[int, bool],
    deadzone: float,
    expo: float,
    smoothing_alpha: float,
    prev: Optional[List[float]],
) -> List[float]:
    out: List[float] = []
    for i, a in enumerate(axes):
        if invert_axes.get(i, False):
            a = -a
        a = clamp(a)
        if deadzone > 0.0 or expo > 0.0:
            a = deadzone_expo(a, deadzone, expo)
        out.append(a)

    # exponential smoothing (optional)
    if prev is None or smoothing_alpha <= 0.0:
        return out
    if smoothing_alpha >= 1.0:
        return out

    n = min(len(prev), len(out))
    for i in range(n):
        out[i] = smoothing_alpha * out[i] + (1.0 - smoothing_alpha) * prev[i]
    return out


def _list_devices() -> int:
    js = PygameJoystick()
    try:
        js.init()
    except Exception as e:
        print(f"pygame init failed: {e}")
        return 2

    devs = js.list_devices()
    if not devs:
        print("no joystick devices found")
        return 1

    print("Available joysticks:")
    for d in devs:
        print(f"  [{d.index}] {d.name}")
    return 0


def run(cfg: InputdConfig, *, log_hz: float = 2.0) -> int:
    out = UdpRawControlsOut.connect(cfg.out_addr)

    js = PygameJoystick()
    js.init()

    prev_axes: Optional[List[float]] = None

    dt = 1.0 / max(1.0, float(cfg.tick_hz))
    next_t = time.monotonic()

    last_log_s = 0.0
    samples = 0
    last_desc = ""

    hb = Heartbeat("inputd", interval_s=1.0)
    ch = ChangeTracker()
    status = StatusEmitter.from_env(default_service="inputd")

    while True:
        ok, desc = js.ensure_open(index=cfg.device_index, name_contains=cfg.name_contains)
        if ok and desc != "ok" and desc != last_desc:
            last_desc = desc
            log.info("joystick connected: %s", desc)

        if ch.changed("connected", bool(ok)):
            log.info("joystick_present=%s", bool(ok))

        connected, axes, buttons = js.read(
            max_axes=cfg.max_axes,
            max_buttons=cfg.max_buttons,
            hat_as_buttons=cfg.hat_as_buttons,
        )

        if connected:
            axes = _postprocess_axes(
                axes,
                invert_axes=cfg.invert_axes,
                deadzone=cfg.deadzone,
                expo=cfg.expo,
                smoothing_alpha=cfg.smoothing_alpha,
                prev=prev_axes,
            )
            prev_axes = axes

            rc = RawControls(
                t_ns=time.monotonic_ns(),
                src=cfg.src,
                axes=axes,
                buttons=buttons,
            )
            out.publish_raw_controls(rc)
            samples += 1
            hb.inc("tx", 1)
        else:
            # when disconnected, keep publishing nothing (policy layer has watchdog)
            prev_axes = None
            hb.inc("drop", 1)

        hb.set("connected", bool(connected))
        hb.set("dev", str(desc) if desc else "")

        now_s = time.monotonic()
        if now_s - last_log_s >= 1.0 / max(1e-6, log_hz):
            last_log_s = now_s
            log.debug("tx samples=%d connected=%s out=%s", samples, connected, cfg.out_addr)

        hb.emit(log)

        if status is not None:
            # Derived, low-rate heartbeat for supervisor birds-eye (does not affect PLC UDP packets).
            level = "OK" if connected else "WARN"
            status.emit_every(
                level=level,
                summary=f"connected={bool(connected)} tx={samples} out={cfg.out_addr}",
                fields={
                    "connected": bool(connected),
                    "tx_samples": int(samples),
                    "out": str(cfg.out_addr),
                    "dev": str(desc) if desc else "",
                },
            )

        next_t += dt
        sleep_s = next_t - time.monotonic()
        if sleep_s > 0:
            time.sleep(sleep_s)
        else:
            next_t = time.monotonic()


def main() -> int:
    ap = argparse.ArgumentParser(prog="steuerung3d.apps.inputd")
    ap.add_argument("--config", default="configs/inputd_gamepad.toml")
    ap.add_argument("--list", action="store_true", help="list joystick devices and exit")
    ap.add_argument("--log-level", default="info", choices=("debug", "info", "warning", "error"))
    args = ap.parse_args()

    bootstrap_logging(role="inputd", log_level=args.log_level)

    if args.list:
        return _list_devices()

    cfg = load_inputd_config(Path(args.config))

    log.info(
        "inputd starting out=%s tick_hz=%.1f device_index=%s name_contains=%s",
        cfg.out_addr,
        cfg.tick_hz,
        cfg.device_index,
        cfg.name_contains,
    )

    try:
        return run(cfg)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
