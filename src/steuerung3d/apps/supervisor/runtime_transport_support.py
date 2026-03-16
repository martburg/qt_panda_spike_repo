from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Protocol

from steuerung3d.core.intents import Intent
from steuerung3d.core.net import parse_hostport
from steuerung3d.core.telemetry import TelemetrySnapshot
from steuerung3d.protocol.udp_channels import UdpIntentOut, UdpTelemetryIn, close_udp_json_endpoint

from .actions_transport import UdpDensiActionOut
from .merge import merge_snapshots
from .models import DensiRemoteAction, OutboundBatch, SupervisorProfile, SupervisorSnapshot

log = logging.getLogger("supervisor")


class _TelemetryInLike(Protocol):
    def drain_telemetry(self, limit: int = 1000) -> list[TelemetrySnapshot]: ...


class _IntentOutLike(Protocol):
    def publish_intent(self, intent: Intent) -> None: ...


class _ActionOutLike(Protocol):
    def publish_action(self, action: DensiRemoteAction) -> None: ...


ActionOutMap = dict[str, _ActionOutLike]


def init_transports(
    *, profile: SupervisorProfile
) -> tuple[UdpTelemetryIn, UdpIntentOut, dict[str, UdpDensiActionOut]]:
    telemetry_in = UdpTelemetryIn.bind(parse_hostport(profile.telem_in))
    intent_out = UdpIntentOut.connect(parse_hostport(profile.intent_out))
    action_outs = {
        axis.unit_id: UdpDensiActionOut.connect(parse_hostport(axis.densi_action_out))
        for axis in profile.axes
        if axis.densi_action_out
    }
    return telemetry_in, intent_out, action_outs


def ingest_telemetry(
    *, telemetry_in: _TelemetryInLike, merged_snapshot: SupervisorSnapshot
) -> SupervisorSnapshot:
    snaps = telemetry_in.drain_telemetry(limit=50)
    if not snaps:
        return merged_snapshot
    return merge_snapshots(merged_snapshot, snaps)


def publish_outbound(
    *,
    outbound: OutboundBatch,
    intent_out: _IntentOutLike,
    action_outs: Mapping[str, _ActionOutLike],
) -> None:
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


def close_transports(
    *,
    telemetry_in: _TelemetryInLike,
    intent_out: _IntentOutLike,
    action_outs: Mapping[str, _ActionOutLike],
) -> None:
    close_udp_json_endpoint(telemetry_in)
    close_udp_json_endpoint(intent_out)
    for tx in action_outs.values():
        close_udp_json_endpoint(tx)
