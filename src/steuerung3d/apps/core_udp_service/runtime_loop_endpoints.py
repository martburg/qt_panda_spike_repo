from __future__ import annotations

from typing import List, Tuple

from steuerung3d.core.net import parse_hostport
from steuerung3d.protocol.udp_channels import (
    UdpControlContextOut,
    UdpIntentIn,
    UdpTelemetryFanout,
    UdpTelemetryOut,
)
from steuerung3d.protocol.udp_plc_channels import UdpPlcCommandOut, UdpPlcTelemetryIn

from .fatal_ui import fatal as _fatal
from .runtime_loop_types import CoreUdpServiceArgs, UdpEndpoints
from .targets import (
    expand_dev_cmd_targets as _expand_dev_cmd_targets,
    expand_targets as _expand_targets,
)


def build_udp_endpoints(*, args: CoreUdpServiceArgs) -> UdpEndpoints | int:
    intent_in_bind = parse_hostport(args.intent_in)
    op_intent_in = UdpIntentIn.bind(intent_in_bind)
    control_context_out = UdpControlContextOut.connect(parse_hostport(args.control_context_target))
    if args.ui_telem_disable and (
        args.ui_telem_target or args.ui_telem_base is not None or int(args.ui_telem_count) > 0
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
    c2_telem_targets = _expand_targets(
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
    dev_cmd_targets = build_dev_cmd_targets(args=args, dev_telem_bind=dev_telem_bind)
    if isinstance(dev_cmd_targets, int):
        return dev_cmd_targets
    return UdpEndpoints(
        intent_in_bind=intent_in_bind,
        op_intent_in=op_intent_in,
        control_context_out=control_context_out,
        ui_telem_targets=ui_telem_targets,
        op_telem_outs=op_telem_outs,
        c2_telem_targets=c2_telem_targets,
        c2_telem_outs=c2_telem_outs,
        c2_fanout=c2_fanout,
        dev_telem_bind=dev_telem_bind,
        dev_telem_in=dev_telem_in,
        dev_cmd_targets=dev_cmd_targets,
        dev_cmd_outs=[UdpPlcCommandOut.connect(t) for t in dev_cmd_targets],
    )


def build_dev_cmd_targets(
    *, args: CoreUdpServiceArgs, dev_telem_bind: tuple[str, int]
) -> list[Tuple[str, int]] | int:
    dev_cmd_targets: List[Tuple[str, int]] = [parse_hostport(s) for s in args.dev_cmd_target]
    if args.dev_cmd_base is not None and int(args.dev_cmd_count) > 0:
        base = int(str(args.dev_cmd_base).strip())
        dev_cmd_targets.extend(
            _expand_dev_cmd_targets(
                str(args.dev_cmd_base), int(args.dev_cmd_count), args.dev_cmd_host
            )
        )
        if dev_telem_bind[0] == "127.0.0.1" and dev_telem_bind[1] in range(
            base, base + int(args.dev_cmd_count)
        ):
            return _fatal(
                f"dev telemetry bind port {dev_telem_bind[1]} overlaps dev-cmd ports {base}..{base + int(args.dev_cmd_count) - 1}. "
                f"Pick a different --dev-telem-in (e.g. 127.0.0.1:{base + 100}) or shift --dev-cmd-base."
            )
    if not dev_cmd_targets:
        if len([a for a in args.axis if a and str(a).strip()]) <= 1:
            return [("127.0.0.1", 52001)]
        return []
    return dev_cmd_targets
