from __future__ import annotations

import logging
from typing import Any

from steuerung3d.core.telemetry import TelemetrySnapshot

from .actions_transport import UdpDensiActionOut
from .merge import merge_snapshots
from .models import OutboundBatch, SupervisorProfile

log = logging.getLogger("supervisor")


def ingest_telemetry(*, telemetry_in: Any, merged_snapshot: TelemetrySnapshot | None):
    snaps = telemetry_in.drain_telemetry(limit=50)
    if not snaps:
        return merged_snapshot
    return merge_snapshots(merged_snapshot, snaps)


def init_transports(*, profile: SupervisorProfile):
    from steuerung3d.protocol.udp_channels import UdpIntentOut, UdpTelemetryIn

    telemetry_in = UdpTelemetryIn.bind(_parse_addr(profile.telem_in))
    intent_out = UdpIntentOut.connect(_parse_addr(profile.intent_out))
    action_outs = {
        axis.unit_id: UdpDensiActionOut.connect(_parse_addr(axis.densi_action_out))
        for axis in profile.axes
        if axis.densi_action_out
    }
    return telemetry_in, intent_out, action_outs


def publish_outbound(*, outbound: OutboundBatch, intent_out: Any, action_outs: dict[str, Any]) -> None:
    for intent in outbound.intents:
        intent_out.publish_intent(intent)
    for unit_id, actions in outbound.densi_actions.items():
        action_out = action_outs.get(unit_id)
        if action_out is None:
            continue
        for action in actions:
            try:
                action_out.publish_action(action)
            except Exception:
                log.exception("failed to publish densi action %s -> %s", unit_id, action)


def close_transports(*, telemetry_in: Any, intent_out: Any, action_outs: dict[str, Any]) -> None:
    for obj in [telemetry_in, intent_out, *list(action_outs.values())]:
        try:
            obj.rx.link.close() if hasattr(obj, "rx") else obj.tx.link.close()
        except Exception:
            pass


def _parse_addr(s: str) -> tuple[str, int]:
    host, port = str(s).rsplit(":", 1)
    return host, int(port)
