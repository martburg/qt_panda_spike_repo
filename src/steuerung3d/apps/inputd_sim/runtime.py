from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Final

from steuerung3d.core.status import StatusEmitter
from steuerung3d.protocol.raw_controls import RawControls
from steuerung3d.protocol.udp_channels import UdpRawControlsOut, close_udp_json_endpoint
from steuerung3d.util.heartbeat import ChangeTracker, Heartbeat

from .config import (
    InputdSimConfig,
    InputdSimSample,
    PreparedInputdSimScenario,
    PreparedInputdSimStep,
    interpolate_axes,
    prepare_scenario,
)
from .control import InputdSimControl, UdpInputdSimControlIn

log = logging.getLogger("inputd_sim")

_IDLE_STEP_NAME: Final[str] = "idle"


@dataclass
class InputdSimRunner:
    prepared: PreparedInputdSimScenario
    active: bool = False
    start_t: float = 0.0
    held_axes: tuple[float, ...] | None = None
    held_buttons: tuple[int, ...] | None = None
    held_step_name: str = _IDLE_STEP_NAME

    def start(self, *, now: float, restart: bool = False) -> bool:
        if self.active and not restart:
            return False
        self.active = True
        self.start_t = float(now)
        self.held_axes = tuple(self.prepared.initial_axes)
        self.held_buttons = tuple(self.prepared.initial_buttons)
        self.held_step_name = _IDLE_STEP_NAME
        return True

    def idle(self) -> None:
        self.active = False
        self.start_t = 0.0
        self.held_axes = tuple(self.prepared.initial_axes)
        self.held_buttons = tuple(self.prepared.initial_buttons)
        self.held_step_name = _IDLE_STEP_NAME

    def sample(self, *, now: float) -> InputdSimSample:
        if not self.active:
            return InputdSimSample(
                axes=tuple(self.held_axes or self.prepared.initial_axes),
                buttons=tuple(self.held_buttons or self.prepared.initial_buttons),
                step_name=self.held_step_name,
                active=False,
            )

        elapsed = max(0.0, float(now) - float(self.start_t))
        offset = 0.0
        last_step: PreparedInputdSimStep | None = None
        for step in self.prepared.steps:
            last_step = step
            step_end = offset + float(step.hold_s)
            if elapsed <= step_end:
                within_step = max(0.0, elapsed - offset)
                axes = interpolate_axes(
                    step.start_axes,
                    step.target_axes,
                    elapsed_s=within_step,
                    ramp_s=float(step.ramp_s),
                )
                self.held_axes = tuple(axes)
                self.held_buttons = tuple(step.target_buttons)
                self.held_step_name = step.name
                return InputdSimSample(
                    axes=tuple(axes),
                    buttons=tuple(step.target_buttons),
                    step_name=step.name,
                    active=True,
                )
            offset = step_end

        self.active = False
        if last_step is None:
            self.held_axes = tuple(self.prepared.initial_axes)
            self.held_buttons = tuple(self.prepared.initial_buttons)
            self.held_step_name = _IDLE_STEP_NAME
            return InputdSimSample(
                axes=tuple(self.prepared.initial_axes),
                buttons=tuple(self.prepared.initial_buttons),
                step_name=_IDLE_STEP_NAME,
                active=False,
            )
        self.held_axes = tuple(last_step.target_axes)
        self.held_buttons = tuple(last_step.target_buttons)
        self.held_step_name = last_step.name
        return InputdSimSample(
            axes=tuple(last_step.target_axes),
            buttons=tuple(last_step.target_buttons),
            step_name=f"{last_step.name}:done",
            active=False,
        )


@dataclass(frozen=True)
class InputdSimObservation:
    active: bool
    step_name: str
    axes: tuple[float, ...]
    buttons: tuple[int, ...]


def _publish_sample(
    *, out: UdpRawControlsOut, cfg: InputdSimConfig, sample: InputdSimSample
) -> None:
    out.publish_raw_controls(
        RawControls(
            t_ns=time.monotonic_ns(),
            src=cfg.src,
            axes=[float(v) for v in sample.axes],
            buttons=[int(v) for v in sample.buttons],
        )
    )


def _apply_control(
    *,
    runner: InputdSimRunner,
    command: InputdSimControl,
    now: float,
) -> str:
    if command.action == "idle":
        runner.idle()
        return "idle"
    if command.action == "restart":
        runner.start(now=now, restart=True)
        return "restart"
    started = runner.start(now=now, restart=False)
    return "start" if started else "start_ignored"


def run(cfg: InputdSimConfig, *, log_hz: float = 2.0) -> int:
    out = UdpRawControlsOut.connect(cfg.out_addr)
    control_in = (
        UdpInputdSimControlIn.bind(cfg.control_in_addr) if cfg.control_in_addr is not None else None
    )
    prepared = prepare_scenario(cfg)
    runner = InputdSimRunner(prepared=prepared)
    if bool(cfg.autostart):
        runner.start(now=time.monotonic(), restart=True)

    dt = 1.0 / max(1.0, float(cfg.tick_hz))
    next_t = time.monotonic()
    last_log_s = 0.0
    last_step_name = ""
    sample_count = 0

    hb = Heartbeat("inputd_sim", interval_s=1.0)
    ch = ChangeTracker()
    status = StatusEmitter.from_env(default_service="inputd_sim")

    try:
        while True:
            now = time.monotonic()
            if control_in is not None:
                for command in control_in.drain_commands(limit=50):
                    outcome = _apply_control(runner=runner, command=command, now=now)
                    log.info("control action=%s outcome=%s", command.action, outcome)

            sample = runner.sample(now=now)
            _publish_sample(out=out, cfg=cfg, sample=sample)
            sample_count += 1
            hb.inc("tx", 1)

            if sample.step_name != last_step_name:
                last_step_name = sample.step_name
                log.info("scenario step=%s active=%s", sample.step_name, bool(sample.active))

            if ch.changed("active", bool(sample.active)):
                log.info("scenario_active=%s", bool(sample.active))

            hb.set("active", bool(sample.active))
            hb.set("step", sample.step_name)
            hb.emit(log)

            if status is not None:
                status.emit_every(
                    level="OK",
                    summary=(
                        f"active={bool(sample.active)} step={sample.step_name} "
                        f"tx={sample_count} out={cfg.out_addr}"
                    ),
                    fields={
                        "active": bool(sample.active),
                        "step": sample.step_name,
                        "tx_samples": int(sample_count),
                        "out": str(cfg.out_addr),
                        "control_in": str(cfg.control_in_addr) if cfg.control_in_addr else "",
                    },
                )

            now_s = time.monotonic()
            if now_s - last_log_s >= 1.0 / max(1e-6, log_hz):
                last_log_s = now_s
                log.debug(
                    "tx samples=%d active=%s step=%s out=%s",
                    sample_count,
                    bool(sample.active),
                    sample.step_name,
                    cfg.out_addr,
                )

            next_t += dt
            sleep_s = next_t - time.monotonic()
            if sleep_s > 0:
                time.sleep(sleep_s)
            else:
                next_t = time.monotonic()
    finally:
        close_udp_json_endpoint(out)
        if control_in is not None:
            close_udp_json_endpoint(control_in)
