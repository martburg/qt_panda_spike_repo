from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, cast

from steuerung3d.core.axis_ids import normalize_axis_id
from steuerung3d.core.joy_facts import extract_joy_facts
from steuerung3d.core.telemetry import DensiTelemetry


@dataclass(frozen=True)
class RuntimeAxisSelection:
    axis: str
    attached: bool


def claim_owner_by_axis(*, densis: Mapping[str, DensiTelemetry], axis_id: str) -> str:
    d = densis.get(str(axis_id or ""))
    if d is None:
        return ""
    return str(getattr(d, "claimed_by_hip", "") or "")


def visible_axis_ids_for_hip(
    *, densis: Mapping[str, DensiTelemetry], hip_id: str, prev_selected: str
) -> list[str]:
    visible: list[str] = []
    hip_id = str(hip_id or "")
    prev_selected = str(prev_selected or "")

    for dev_id, d in densis.items():
        axis_id = str(dev_id or "").strip()
        if not axis_id:
            continue

        owner = str(getattr(d, "claimed_by_hip", "") or "")
        online = bool(getattr(d, "online", False))

        if online and owner in ("", hip_id):
            visible.append(axis_id)
            continue

        if axis_id == prev_selected and owner == hip_id:
            visible.append(axis_id)

    return sorted({x for x in visible if x.strip()})


def authoritative_selected_axis(
    *, densis: Mapping[str, DensiTelemetry], hip_id: str, selected_axis: str, prev_selected: str
) -> str:
    hip_id = str(hip_id or "")
    selected_axis = str(selected_axis or "")
    prev_selected = str(prev_selected or "")

    if selected_axis:
        owner = claim_owner_by_axis(densis=densis, axis_id=selected_axis)
        if owner == hip_id:
            return selected_axis

    if prev_selected:
        owner = claim_owner_by_axis(densis=densis, axis_id=prev_selected)
        if owner == hip_id:
            return prev_selected

    return ""


def resolve_runtime_axis(*, selected_axis: str, fixed_axis: str) -> RuntimeAxisSelection:
    selected = normalize_axis_id(selected_axis)
    fixed = normalize_axis_id(fixed_axis)
    axis = normalize_axis_id(selected or fixed)
    attached = bool(selected) or bool(fixed)
    return RuntimeAxisSelection(axis=axis, attached=attached)


def joy_selected_for_axis(*, joy: object | None, axis_id: str) -> bool:
    axis = normalize_axis_id(axis_id)
    if not axis:
        return False

    selected_axes: tuple[str, ...] = ()
    if joy is not None:
        raw = getattr(joy, "selected_axes", None)
        if raw is not None:
            # Keep this permissive: accept any iterable of values and normalize to strings.
            try:
                it = cast(Iterable[object], raw)
                selected_axes = tuple(str(x) for x in it)
            except TypeError:
                selected_axes = ()

    if selected_axes:
        selected_axis_set = {
            normalize_axis_id(str(x).strip()) for x in selected_axes if str(x).strip()
        }
        return axis in selected_axis_set

    facts = extract_joy_facts(joy)
    return bool(facts.select_hip) and bool(axis)


def joy_speed_for_axis(*, joy: object | None, axis_id: str) -> float:
    facts = extract_joy_facts(joy)
    return float(facts.soll_speed) if joy_selected_for_axis(joy=joy, axis_id=axis_id) else 0.0


def resolve_motion_axis_id(
    *,
    axis_id: str,
    axis_ids: list[str],
    joy_deadman: bool,
    joy_select_hip: bool,
    axes: Mapping[str, object],
) -> str:
    """Resolve motion axis id.

    Normally, motion is directed to the currently attached axis (``axis_id``).
    For single-axis bring-up, we allow motion even when the UI isn't fully
    configured yet, but only when it would be unambiguous.
    """

    motion_axis_id = normalize_axis_id(axis_id)
    if not motion_axis_id and len(axis_ids) == 1 and joy_deadman and joy_select_hip:
        actionable: list[str] = []
        for axis_key in axis_ids:
            ax = axes.get(axis_key)
            if ax is None:
                continue

            in_scope = getattr(ax, "in_scope", True)
            if in_scope is None:
                in_scope = True
            if not bool(in_scope):
                continue

            if bool(getattr(ax, "fault", False)):
                continue

            actionable.append(str(axis_key))

        if len(actionable) == 1:
            motion_axis_id = actionable[0]

    return str(motion_axis_id or "")
