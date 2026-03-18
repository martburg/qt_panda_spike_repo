"""Helpers for HiP ↔ target attachment discovery.

Current phase exposes only leaf targets backed by live DenSi devices. The
helper intentionally talks in terms of *targets* so future group targets can be
added without rewriting the HiP picker pipeline.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from steuerung3d.core.axis_ids import normalize_axis_id
from steuerung3d.core.telemetry import TelemetrySnapshot


def _as_map(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        return {}
    return {str(k): v for k, v in value.items()}


def _first_str(value: object) -> str:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)) and value:
        return str(value[0] or "")
    return ""


def claim_owner_from_snapshot(snap: TelemetrySnapshot, target_id: str) -> str:
    """Return the best-known owner for *target_id* from a telemetry snapshot."""

    target_id = normalize_axis_id(target_id)
    if not target_id:
        return ""

    densis = _as_map(getattr(snap, "densis", None))
    d = densis.get(target_id)
    if d is not None:
        owner = str(getattr(d, "claimed_by_hip", "") or "")
        if owner:
            return owner

    holders = _as_map(getattr(snap, "lease_axis_holders", None))
    owner = _first_str(holders.get(target_id))
    if owner:
        return owner

    lease_axis = _as_map(getattr(snap, "lease_axis", None))
    owner = _first_str(lease_axis.get(target_id))
    if owner:
        return owner

    return ""


def list_attachable_leaf_targets(
    snap: TelemetrySnapshot,
    *,
    hip_id: str,
    include_selected: str = "",
) -> list[str]:
    """Return the HiP picker candidates for the current 1:1 attach phase.

    Rules for the current semantic step:
    - only live DenSis are presented as attachable leaf targets
    - targets claimed by another HiP are hidden
    - targets claimed by *this* HiP remain visible
    - the currently selected target may stay visible even if it went offline so
      the operator can intentionally detach it
    """

    hip_id = str(hip_id or "")
    include_selected = normalize_axis_id(include_selected)

    densis = _as_map(getattr(snap, "densis", None))

    out: list[str] = []
    seen: set[str] = set()
    for dev_id, d in densis.items():
        target_id = normalize_axis_id(dev_id)
        if not target_id or target_id in seen:
            continue
        owner = claim_owner_from_snapshot(snap, target_id)
        online = bool(getattr(d, "online", False)) if d is not None else False
        if online and (not owner or owner == hip_id):
            out.append(target_id)
            seen.add(target_id)

    if include_selected and include_selected not in seen:
        out.append(include_selected)

    return sorted(out)
