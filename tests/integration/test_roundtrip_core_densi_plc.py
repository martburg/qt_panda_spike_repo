from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import time
from contextlib import closing
from pathlib import Path
from typing import Callable

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"


from steuerung3d.core.intents import ParamEditBegin, ParamWrite
from steuerung3d.protocol.legacy_plc import encode_uplink
from steuerung3d.protocol.plc_codec import decode_downlink
from steuerung3d.protocol.udp_channels import UdpIntentOut, UdpTelemetryIn


def _pick_free_udp_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_DGRAM)) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _start_core(
    *, axis: str, intent_port: int, ui_port: int, dev_telem_port: int, dev_cmd_port: int
) -> subprocess.Popen[bytes]:
    # NOTE: relies on core supporting --intent-in (added by earlier patch).
    cmd = [
        sys.executable,
        "-m",
        "steuerung3d.apps.core_udp_service",
        "--log-level",
        "warning",
        "--dt",
        "0.02",
        "--axis",
        axis,
        "--intent-in",
        f"127.0.0.1:{intent_port}",
        "--ui-telem-target",
        f"127.0.0.1:{ui_port}",
        "--dev-cmd-base",
        str(dev_cmd_port),
        "--dev-cmd-count",
        "1",
        "--dev-telem-in",
        f"127.0.0.1:{dev_telem_port}",
    ]
    # Quiet logs to keep pytest output clean.
    env = os.environ.copy()
    py_path = str(SRC_DIR)
    env["PYTHONPATH"] = py_path + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    return subprocess.Popen(
        cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=str(REPO_ROOT), env=env
    )


def _wait_for(condition: Callable[[], bool], timeout_s: float = 5.0, sleep_s: float = 0.02) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        if condition():
            return True
        time.sleep(sleep_s)
    return False


class _DenSiProbe(threading.Thread):
    """
    Headless DenSi PLC-wire probe:

    - Listens for core downlink telegrams on cmd_port.
    - Periodically emits uplink telegrams to telem_target_port.
    - If it observes a write telegram (Modus=='w'), it reflects the written params
      back in subsequent uplink frames.
    """

    def __init__(self, *, axis: str, cmd_port: int, telem_target_port: int):
        super().__init__(daemon=True)
        self.axis = axis
        self.cmd_port = int(cmd_port)
        self.telem_target_port = int(telem_target_port)
        self._stop = threading.Event()
        self.last_seen_downlink: dict[str, str] | None = None
        self.lifetick = 1000

        self._cmd_rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._cmd_rx.settimeout(0.05)
        self._cmd_rx.bind(("127.0.0.1", self.cmd_port))

        self._tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def stop(self):
        self._stop.set()
        try:
            self._cmd_rx.close()
        except Exception:
            pass
        try:
            self._tx.close()
        except Exception:
            pass

    def run(self):
        next_tx = time.time()
        # Defaults
        filt_p = 0.0
        filt_i = 0.0
        filt_d = 0.0
        filt_il = 0.0

        while not self._stop.is_set():
            # Receive downlink if present
            try:
                data, _ = self._cmd_rx.recvfrom(4096)
                d = decode_downlink(data)
                if d:
                    fields = {str(k): v for k, v in dict(d.fields).items()}
                    self.last_seen_downlink = fields
                    if d.is_write:
                        # Reflect written filter fields if present.
                        def _f(name: str, cur: float, fields_map: dict[str, str]) -> float:
                            v = fields_map.get(name, "")
                            if v == "":
                                return cur
                            try:
                                return float(v)
                            except Exception:
                                return cur

                        filt_p = _f("FilterP", filt_p, fields)
                        filt_i = _f("FilterI", filt_i, fields)
                        filt_d = _f("FilterD", filt_d, fields)
                        filt_il = _f("FilterIL", filt_il, fields)
            except socket.timeout:
                pass
            except OSError:
                # socket closed
                break

            # Periodic uplink
            now = time.time()
            if now >= next_tx:
                self.lifetick = (self.lifetick + 1) & 0xFFFF
                upl = encode_uplink(
                    fields={
                        "OwnPID": 0,
                        "LifetickUItx": int(self.lifetick),
                        "Name": self.axis,
                        "EStopStatus": 0,
                        "FilterP": float(filt_p),
                        "FilterI": float(filt_i),
                        "FilterD": float(filt_d),
                        "FilterIL": float(filt_il),
                        "RampenformUI": 0,
                        "PosMaxHardUI": 300.0,
                    },
                    tail={
                        "SystemTime": 603951104,
                        "PosWinUI": 0.01,
                        "VelWinUI": 0.01,
                        "AccTotUI": 5.0,
                    },
                )
                try:
                    self._tx.sendto(
                        upl.encode("utf-8", errors="replace"), ("127.0.0.1", self.telem_target_port)
                    )
                except OSError:
                    break
                next_tx = now + 0.02

            time.sleep(0.002)


@pytest.mark.integration
def test_core_densi_param_write_roundtrip_plc():
    """
    Start core and a headless DenSi PLC-wire probe.

    Send ParamEditBegin + ParamWrite intent to core and verify:
      - core emits a downlink Modus=='w' telegram (probe sees it)
      - probe reflects written filter params in uplink
      - core forwards them to UI telemetry (snap.params contains internal keys)
    """
    axis = "Anton"
    intent_port = _pick_free_udp_port()
    ui_port = _pick_free_udp_port()
    dev_telem_port = _pick_free_udp_port()
    dev_cmd_port = _pick_free_udp_port()

    core = _start_core(
        axis=axis,
        intent_port=intent_port,
        ui_port=ui_port,
        dev_telem_port=dev_telem_port,
        dev_cmd_port=dev_cmd_port,
    )

    probe = _DenSiProbe(axis=axis, cmd_port=dev_cmd_port, telem_target_port=dev_telem_port)
    probe.start()

    try:
        telem_in = UdpTelemetryIn.bind(("127.0.0.1", ui_port))
        intent_out = UdpIntentOut.connect(("127.0.0.1", intent_port))

        # Ensure core has seen at least one telemetry frame before we start edit/write.
        rx_counts = {"snaps": 0, "axis_hits": 0}

        def _axis_seen() -> bool:
            snaps = telem_in.drain_telemetry(limit=100)
            rx_counts["snaps"] += len(snaps)
            hit = any(axis in (s.axes or {}) for s in snaps)
            if hit:
                rx_counts["axis_hits"] += 1
            return hit

        assert _wait_for(_axis_seen), (
            "Core did not publish UI telemetry for axis within timeout. "
            f"snaps_rx={rx_counts['snaps']} probe_lifetick={probe.lifetick} "
            f"last_downlink={'yes' if probe.last_seen_downlink else 'no'}"
        )

        desired = {"P": 6.3, "I": 0.0, "D": 0.0, "IL": 0.0}

        # Mimic HiP workflow: begin edit, then write values.
        intent_out.publish_intent(
            ParamEditBegin(
                axis_id=axis,
                hip_id="test",
                group="filter",
                req_id="req-edit-1",
                session_id="sess-test",
            )
        )
        time.sleep(0.05)
        intent_out.publish_intent(
            ParamWrite(
                axis_id=axis,
                hip_id="test",
                group="filter",
                values=desired,
                req_id="req-write-1",
                session_id="sess-test",
            )
        )

        # Wait for probe to observe a write telegram.
        def _saw_write():
            f = probe.last_seen_downlink or {}
            return str(f.get("Modus", "")) == "w"

        assert _wait_for(_saw_write, timeout_s=2.5), (
            "core did not emit Modus=='w' downlink for ParamWrite"
        )

        # Wait for UI telemetry to reflect the written filter P under internal key 'P'.
        got_p: dict[str, float | None] = {"v": None}

        def _p_reflected():
            snaps = telem_in.drain_telemetry(limit=50)
            for s in snaps:
                if not getattr(s, "params", None):
                    continue
                p = s.params.get("P")
                if p is None:
                    continue
                try:
                    if abs(float(p) - float(desired["P"])) < 1e-6:
                        got_p["v"] = float(p)
                        return True
                except Exception:
                    continue
            return False

        assert _wait_for(_p_reflected, timeout_s=3.0), (
            "UI telemetry did not reflect written filter P parameter"
        )

    finally:
        probe.stop()
        core.terminate()
        core.wait(timeout=2.0)
