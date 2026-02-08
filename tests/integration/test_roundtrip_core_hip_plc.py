from __future__ import annotations

import sys
import time
import socket
import subprocess
from contextlib import closing

import pytest

from steuerung3d.protocol.udp_channels import UdpTelemetryIn, UdpIntentOut
from steuerung3d.core.intents import EchoLifeTick
from steuerung3d.protocol.legacy_plc import encode_uplink
from steuerung3d.protocol.plc_codec import decode_downlink


def _pick_free_udp_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_DGRAM)) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _start_core(*, axis: str, intent_port: int, ui_port: int, dev_telem_port: int, dev_cmd_port: int) -> subprocess.Popen:
    # NOTE: relies on core supporting --intent-in and --ui-telem-target.
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
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _wait_for(condition, timeout_s: float = 3.5, sleep_s: float = 0.02) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        if condition():
            return True
        time.sleep(sleep_s)
    return False


@pytest.mark.integration
def test_core_hip_livetick_echo_roundtrip_plc():
    """
    Start core, emulate HiP (UDP JSON telem-in + intent-out), inject a PLC uplink
    line and verify the echoed LifeTick comes back in the PLC downlink.

    Guards:
      - A PLC uplink telegram that carries LifetickUItx makes it through Core->UI telemetry
        (either as TelemetrySnapshot.tick or as AxisTelemetry.device_tick, depending on version).
      - HiP EchoLifeTick intent is accepted by core and mirrored into PLC downlink LifetickUIrx.
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

    cmd_rx = None
    try:
        # Receive core downlink (PLC command telegrams)
        cmd_rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        cmd_rx.settimeout(0.25)
        cmd_rx.bind(("127.0.0.1", dev_cmd_port))

        telem_in = UdpTelemetryIn.bind(("127.0.0.1", ui_port))
        intent_out = UdpIntentOut.connect(("127.0.0.1", intent_port))

        # Build a "realistic enough" uplink: full field-count + EOD + tail.
        lifetick = 20400
        upl = encode_uplink(
            fields={
                "OwnPID": 0,
                "LifetickUItx": lifetick,
                "Name": axis,
                "EStopStatus": 0,
                "PosMaxHardUI": 300.0,
                "FilterP": 6.3,
                "RampenformUI": 0,
            },
            tail={
                "SystemTime": 603951104,
                "PosWinUI": 0.01,
                "VelWinUI": 0.01,
                "AccTotUI": 5.0,
            },
        )
        upl_bytes = upl.encode("utf-8", errors="replace")

        # Robust against core startup races: keep injecting uplink while waiting.
        observed = {
            "snap_tick": None,
            "axis_tick": None,
            "axis_key": None,
            "p": None,
        }

        with closing(socket.socket(socket.AF_INET, socket.SOCK_DGRAM)) as tx:

            def _tick_seen() -> bool:
                # Re-inject each polling step so we don't lose the first datagram during startup.
                try:
                    tx.sendto(upl_bytes, ("127.0.0.1", dev_telem_port))
                except Exception:
                    pass

                snaps = telem_in.drain_telemetry(limit=200)
                for s in snaps:
                    # Snapshot tick path
                    st = 0
                    try:
                        st = int(getattr(s, "tick", 0) or 0)
                    except Exception:
                        st = 0
                    if st:
                        observed["snap_tick"] = st

                    # Params evidence (helps distinguish "uplink not processed" vs "tick not forwarded")
                    try:
                        params = getattr(s, "params", None) or {}
                        if "P" in params:
                            observed["p"] = params.get("P")
                    except Exception:
                        pass

                    # Axis tick path: accept exact axis key match OR single-axis snapshots.
                    axes = getattr(s, "axes", None) or {}
                    ax_key = None
                    if axis in axes:
                        ax_key = axis
                    elif len(axes) == 1:
                        ax_key = next(iter(axes.keys()))

                    if ax_key is not None:
                        observed["axis_key"] = ax_key
                        at = 0
                        try:
                            at = int(getattr(axes[ax_key], "device_tick", 0) or 0)
                        except Exception:
                            at = 0
                        if at:
                            observed["axis_tick"] = at

                        if st == lifetick or at == lifetick:
                            return True

                return False

            assert _wait_for(_tick_seen, timeout_s=3.5), (
                "Did not observe injected LifetickUItx in UI telemetry "
                f"(last snap.tick={observed['snap_tick']}, last axis.device_tick={observed['axis_tick']}, "
                f"axis_key={observed['axis_key']}, last params.P={observed['p']})"
            )

        # Send EchoLifeTick intent from HiP to Core (mirror the value we injected).
        intent_out.publish_intent(EchoLifeTick(axis_id=axis, value=int(lifetick), hip_id="test"))

        # Verify core mirrors the echoed value into PLC downlink LifetickUIrx.
        def _echo_seen():
            try:
                data, _addr = cmd_rx.recvfrom(4096)
            except (socket.timeout, TimeoutError, OSError):
                return False
            d = decode_downlink(data)
            if not d:
                return False
            rx = d.fields.get("LifetickUIrx", "")
            try:
                return int(float(rx)) == int(lifetick)
            except Exception:
                return False

        assert _wait_for(_echo_seen, timeout_s=3.5), "Did not observe PLC downlink LifetickUIrx mirrored from EchoLifeTick"

    finally:
        try:
            if cmd_rx is not None:
                cmd_rx.close()
        except Exception:
            pass
        try:
            core.terminate()
            core.wait(timeout=2.0)
        except Exception:
            pass
