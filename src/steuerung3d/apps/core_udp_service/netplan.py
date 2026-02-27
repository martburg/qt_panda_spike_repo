from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from steuerung3d.core.net import parse_hostport
from steuerung3d.protocol.udp_channels import UdpIntentIn, UdpTelemetryOut, UdpTelemetryFanout
from steuerung3d.protocol.udp_plc_channels import UdpPlcTelemetryIn, UdpPlcCommandOut

from .fatal_ui import fatal as _fatal
from .targets import expand_dev_cmd_targets as _expand_dev_cmd_targets
from .targets import expand_targets as _expand_targets


@dataclass(frozen=True)
class UdpPlan:
    # Operator intents
    intent_in_bind: Tuple[str, int]
    op_intent_in: UdpIntentIn

    # Operator telemetry (one target per axis, validated later)
    ui_telem_targets: List[Tuple[str, int]]
    op_telem_outs: List[UdpTelemetryOut]

    # Optional secondary telemetry fanout
    c2_telem_targets: List[Tuple[str, int]]
    c2_fanout: UdpTelemetryFanout | None

    # Device telemetry in
    dev_telem_bind: Tuple[str, int]
    dev_telem_in: UdpPlcTelemetryIn

    # Device command outs
    dev_cmd_targets: List[Tuple[str, int]]
    dev_cmd_outs: List[UdpPlcCommandOut]


def build_udp_plan(*, args) -> UdpPlan | int:
    """Build UDP binds/connects from CLI args.

    Structural helper: extracted from runtime_loop to keep the main loop readable.
    Validation of axis<->target counts happens in runtime_loop.
    """

    intent_in_bind = parse_hostport(args.intent_in)
    op_intent_in = UdpIntentIn.bind(intent_in_bind)

    # UI telemetry targets
    if args.ui_telem_disable and (
        args.ui_telem_target
        or args.ui_telem_base is not None
        or int(args.ui_telem_count) > 0
    ):
        return _fatal("UI telemetry disabled but UI targets were provided.")

    ui_telem_targets = _expand_targets(
        args.ui_telem_target,
        base=args.ui_telem_base,
        count=int(args.ui_telem_count),
        base_host=args.ui_telem_host,
        default_target=None if args.ui_telem_disable else ("127.0.0.1", 51002),
    )
    op_telem_outs = [UdpTelemetryOut.connect(t) for t in ui_telem_targets]

    c2_telem_targets: List[Tuple[str, int]] = _expand_targets(
        args.c2_telem_target,
        base=args.c2_telem_base,
        count=int(args.c2_telem_count),
        base_host=args.c2_telem_host,
        default_target=None,
    )
    c2_telem_outs = [UdpTelemetryOut.connect(t) for t in c2_telem_targets]
    c2_fanout = UdpTelemetryFanout(outs=c2_telem_outs) if c2_telem_outs else None

    dev_telem_bind = parse_hostport(args.dev_telem_in)
    dev_telem_in = UdpPlcTelemetryIn.bind(dev_telem_bind)

    # Device command broadcast targets (N DenSi apps each binding a unique command port)
    dev_cmd_targets: List[Tuple[str, int]] = []
    for s in args.dev_cmd_target:
        dev_cmd_targets.append(parse_hostport(s))

    if args.dev_cmd_base is not None and int(args.dev_cmd_count) > 0:
        base = int(str(args.dev_cmd_base).strip())
        dev_cmd_targets.extend(
            _expand_dev_cmd_targets(str(args.dev_cmd_base), int(args.dev_cmd_count), args.dev_cmd_host)
        )

        # Guard against accidental port overlap (common on Windows).
        if dev_telem_bind[0] == "127.0.0.1" and dev_telem_bind[1] in range(base, base + int(args.dev_cmd_count)):
            return _fatal(
                f"dev telemetry bind port {dev_telem_bind[1]} overlaps dev-cmd ports {base}..{base + int(args.dev_cmd_count) - 1}. "
                f"Pick a different --dev-telem-in (e.g. 127.0.0.1:{base + 100}) or shift --dev-cmd-base."
            )

    if not dev_cmd_targets:
        # Default only for single-axis convenience. Multi-axis requires explicit per-axis targets.
        if len([a for a in args.axis if a and str(a).strip()]) <= 1:
            dev_cmd_targets = [("127.0.0.1", 52001)]
        else:
            dev_cmd_targets = []

    dev_cmd_outs = [UdpPlcCommandOut.connect(t) for t in dev_cmd_targets]

    return UdpPlan(
        intent_in_bind=intent_in_bind,
        op_intent_in=op_intent_in,
        ui_telem_targets=ui_telem_targets,
        op_telem_outs=op_telem_outs,
        c2_telem_targets=c2_telem_targets,
        c2_fanout=c2_fanout,
        dev_telem_bind=dev_telem_bind,
        dev_telem_in=dev_telem_in,
        dev_cmd_targets=dev_cmd_targets,
        dev_cmd_outs=dev_cmd_outs,
    )
