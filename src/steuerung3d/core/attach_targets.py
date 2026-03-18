"""Helpers for HiP ↔ target attachment discovery.

Current phase exposes only leaf targets backed by live DenSi devices. The
helper intentionally talks in terms of *targets* so future group targets can be
added without rewriting the HiP picker pipeline.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import cast

from steuerung3d.core.axis_ids import normalize_axis_id
from steuerung3d.core.telemetry import TelemetrySnapshot


def _as_map(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        return {}
    mapping = cast(Mapping[object, object], value)
    return {str(k): v for k, v in mapping.items()}


def _first_str(value: object) -> str:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)) and value:
        seq = cast(Sequence[object], value)
        return str(seq[0] or "")
    return ""


def claim_owner_from_snapshot(snap: TelemetrySnapshot, target_id: str) -> str:
    target_id = normalize_axis_id(target_id)
    if not target_id:
        return ""

    d = snap.densis.get(target_id)
    if d is not None:
        owner = str(d.claimed_by_hip or "")
        if owner:
            return owner

    owner = _first_str(snap.lease_axis_holders.get(target_id))
    if owner:
        return owner

    owner = _first_str(snap.lease_axis.get(target_id))
    if owner:
        return owner

    return ""


def list_attachable_leaf_targets(
    snap: TelemetrySnapshot,
    *,
    hip_id: str,
    include_selected: str = "",
) -> list[str]:
    hip_id = str(hip_id or "")
    include_selected = normalize_axis_id(include_selected)

    out: list[str] = []
    seen: set[str] = set()
    for dev_id, d in snap.densis.items():
        target_id = normalize_axis_id(dev_id)
        if not target_id or target_id in seen:
            continue
        owner = claim_owner_from_snapshot(snap, target_id)
        online = bool(d.online)
        if online and (not owner or owner == hip_id):
            out.append(target_id)
            seen.add(target_id)

    if include_selected and include_selected not in seen:
        out.append(include_selected)

    return sorted(out)


_STRICT_KEEP = _as_map
