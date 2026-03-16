from __future__ import annotations

import logging
from typing import Any

from steuerung3d.core.net import parse_hostport
from steuerung3d.protocol.udp_channels import UdpIntentOut, UdpTelemetryIn

from .actions_transport import UdpDensiActionOut
from .merge import merge_snapshots
from .models import SupervisorProfile

log = logging.getLogger("supervisor")


def init_transports(*, profile: SupervisorProfile) -> tuple[Any, Any, dict[str, Any]]:
    telemetry_in = UdpTelemetryIn.bind(parse_hostport(profile.telem_in))
    intent_out = UdpIntentOut.connect(parse_hostport(profile.intent_out))
    action_outs = {
        axis.unit_id: UdpDensiActionOut.connect(parse_hostport(axis.densi_action_out))
        for axis in profile.axes
        if axis.densi_action_out
    }
    return telemetry_in, intent_out, action_outs


def ingest_telemetry(*, telemetry_in: Any, merged_snapshot: Any) -> Any:
    snaps = telemetry_in.drain_telemetry(limit=50)
    if not snaps:
        return merged_snapshot
    return merge_snapshots(merged_snapshot, snaps)


def publish_outbound(*, outbound: Any, intent_out: Any, action_outs: dict[str, Any]) -> None:
    for intent in outbound.intents:
        try:
            intent_out.publish_intent(intent)
        except Exception:
            log.exception("failed to publish intent %r", intent)

    for pair_id, actions in outbound.densi_actions.items():
        tx = action_outs.get(pair_id)
        if tx is None:
            continue
        for action in actions:
            try:
                tx.publish_action(action)
            except Exception:
                log.exception("failed to publish densi action %s -> %s", pair_id, action)


def close_transports(*, telemetry_in: Any, intent_out: Any, action_outs: dict[str, Any]) -> None:
    try:
        telemetry_in.rx.link.close()
    except Exception:
        pass

    try:
        intent_out.tx.link.close()
    except Exception:
        pass

    for tx in action_outs.values():
        try:
            tx.tx.link.close()
        except Exception:
            pass
