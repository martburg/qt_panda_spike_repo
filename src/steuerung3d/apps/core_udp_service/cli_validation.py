from __future__ import annotations

from typing import List, Tuple


def uniq_axes_or_error(axis_ids: List[str]) -> tuple[list[str], str | None]:
    """Return (unique_axes, error_message_if_any)."""

    seen = set()
    dupes: list[str] = []
    uniq: list[str] = []
    for a in axis_ids:
        k = a
        if k in seen:
            dupes.append(k)
            continue
        seen.add(k)
        uniq.append(k)
    if dupes:
        msg = (
            "Duplicate --axis entries are not allowed (strict per-axis routing).\n\n"
            f"Axes provided: {axis_ids}\n"
            f"Duplicates: {sorted(set(dupes))}"
        )
        return axis_ids, msg
    return uniq, None


def validate_dev_cmd_targets(
    *,
    axis_ids: list[str],
    dev_cmd_targets: list[Tuple[str, int]],
) -> str | None:
    """Return an error message if strict per-axis command routing is violated."""

    if len(axis_ids) > 1:
        if len(dev_cmd_targets) != len(axis_ids):
            msg = (
                "Multi-axis run requires one --dev-cmd-target per axis (no broadcast).\n\n"
                f"Axes ({len(axis_ids)}): {', '.join(axis_ids)}\n"
                f"Targets provided ({len(dev_cmd_targets)}): {dev_cmd_targets}\n\n"
                "Fix: provide N targets, e.g.\n"
                "  --dev-cmd-target 172.16.17.1:50010 --dev-cmd-target 172.16.17.2:50010 ...\n"
                "or use a local sim range, e.g.\n"
                f"  --dev-cmd-base 52001 --dev-cmd-count {len(axis_ids)}\n\n"
                "Note: --dev-telem-in must NOT overlap the dev-cmd port range."
            )
            return msg
    else:
        if len(dev_cmd_targets) != 1:
            msg = (
                "Single-axis run requires exactly one --dev-cmd-target.\n\n"
                f"Axis: {axis_ids[0] if axis_ids else 'X'}\n"
                f"Targets provided ({len(dev_cmd_targets)}): {dev_cmd_targets}"
            )
            return msg
    return None


def validate_ui_telem_targets(
    *,
    ui_telem_disable: bool,
    axis_ids: list[str],
    ui_telem_targets: list[Tuple[str, int]],
    mode: str = "per_axis",
) -> str | None:
    if ui_telem_disable:
        return None

    mode = str(mode or "per_axis").strip().lower()
    if mode not in ("per_axis", "fanout"):
        return f"Unsupported UI telemetry mode: {mode}"

    if mode == "fanout":
        if len(ui_telem_targets) < 1:
            return (
                "Fanout UI telemetry mode requires at least one UI telemetry target.\n\n"
                "Fix: provide one or more --ui-telem-target values or use --ui-telem-base/--ui-telem-count."
            )
        return None

    if len(axis_ids) > 1:
        if len(ui_telem_targets) != len(axis_ids):
            msg = (
                "Multi-axis run requires one UI telemetry target per axis in per_axis mode.\n\n"
                f"Axes ({len(axis_ids)}): {', '.join(axis_ids)}\n"
                f"UI Telemetry targets provided ({len(ui_telem_targets)}): {ui_telem_targets}\n\n"
                "Fix: provide N targets, e.g.\n"
                "  --ui-telem-target 127.0.0.1:51002 --ui-telem-target 127.0.0.1:51003 ...\n"
                "or use a local range, e.g.\n"
                f"  --ui-telem-base 51002 --ui-telem-count {len(axis_ids)}\n"
                "or switch to fanout mode for pooled HiPs:\n"
                "  --ui-telem-mode fanout\n"
            )
            return msg
    else:
        if len(ui_telem_targets) != 1:
            msg = (
                "Single-axis run requires exactly one UI telemetry target in per_axis mode.\n\n"
                f"Axis: {axis_ids[0] if axis_ids else 'X'}\n"
                f"Targets provided ({len(ui_telem_targets)}): {ui_telem_targets}"
            )
            return msg
    return None
