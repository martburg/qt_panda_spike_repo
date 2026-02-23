from steuerung3d.protocol.transport import InMemTransport
from steuerung3d.core.intents import SetEstop
from steuerung3d.core.telemetry import TelemetrySnapshot, AxisTelemetry


def test_inmem_transport_roundtrip():
    tr = InMemTransport()

    tr.publish_intent(SetEstop(estop=True))
    intents = tr.drain_intents()
    assert len(intents) == 1

    snap = TelemetrySnapshot(
        tick=1,
        t_s=0.01,
        mode="IDLE",
        core_mode="IDLE",
        estop=True,
        fault=False,
        axes={"X": AxisTelemetry(pos=0.0, vel=0.0, enabled=False, fault=False)},
    )
    tr.publish_telemetry(snap)
    snaps = tr.drain_telemetry()
    assert len(snaps) == 1
    assert snaps[0].estop is True
