from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import cast

from steuerung3d.core.net import parse_hostport

from .models import SupervisorProfile
from .row_estate import estate_from_word


def _as_str_object_mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        return {}
    return cast(Mapping[str, object], value)


def _mapping_attr(obj: object, name: str) -> Mapping[str, object]:
    return _as_str_object_mapping(getattr(obj, name, None))


def _mapping_value(mapping: Mapping[str, object], key: str) -> object | None:
    return mapping.get(key)


def _text_attr(obj: object, name: str) -> str:
    return str(getattr(obj, name, "") or "")


def _coerce_float(value: object) -> float | None:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except Exception:
            return None
    return None


def _coerce_int(value: object) -> int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except Exception:
            return None
    return None


def _float_attr(obj: object, name: str, default: float = 0.0) -> float:
    raw = getattr(obj, name, default)
    value = _coerce_float(raw)
    if value is None:
        return float(default)
    return value


def _int_attr(obj: object, name: str, default: int = 0) -> int:
    raw = getattr(obj, name, default)
    value = _coerce_int(raw)
    if value is None:
        return int(default)
    return value


def infer_observer_telemetry_candidates(profile: SupervisorProfile) -> tuple[tuple[str, int], ...]:
    host, port = parse_hostport(profile.telem_in)
    highest_offset = max(1, len(tuple(profile.axes or ())))
    return tuple((host, int(port) + offset) for offset in range(1, highest_offset + 1))


def infer_hip_observer_telemetry_candidates(
    profile: SupervisorProfile,
) -> tuple[tuple[str, int], ...]:
    host, port = parse_hostport(profile.telem_in)
    reserved_offsets = 1 + len(tuple(profile.axes or ()))
    return ((host, int(port) + reserved_offsets + 1),)


def parse_system_time_token(token: str) -> datetime | None:
    raw = str(token or "").strip()
    if not raw or not raw.endswith(" ms"):
        return None
    stem = raw[:-3].rstrip()
    try:
        dt_part, ms_part = stem.rsplit(" ", 1)
        return datetime.strptime(f"{dt_part}.{int(ms_part):03d}", "%d-%m-%Y %H:%M:%S.%f")
    except Exception:
        return None


def system_time_tokens_advanced(previous: str, current: str) -> bool:
    prev_raw = str(previous or "").strip()
    curr_raw = str(current or "").strip()
    if not prev_raw or not curr_raw:
        return False
    prev_dt = parse_system_time_token(prev_raw)
    curr_dt = parse_system_time_token(curr_raw)
    if prev_dt is not None and curr_dt is not None:
        return curr_dt > prev_dt
    return curr_raw != prev_raw


def extract_axis_system_time_tokens(snap: object, axis_ids: Sequence[str]) -> dict[str, str]:
    tail_by_axis = _mapping_attr(snap, "axis_plc_uplink_tail")
    tokens: dict[str, str] = {}
    for axis_id in axis_ids:
        axis_tail = _as_str_object_mapping(_mapping_value(tail_by_axis, axis_id))
        token = str(_mapping_value(axis_tail, "SystemTime") or "").strip()
        if token:
            tokens[str(axis_id)] = token
    return tokens


def extract_axis_device_ticks(snap: object, axis_ids: Sequence[str]) -> dict[str, int]:
    axes = _mapping_attr(snap, "axes")
    ticks: dict[str, int] = {}
    for axis_id in axis_ids:
        axis_telem = _mapping_value(axes, axis_id)
        if axis_telem is None:
            continue
        ticks[str(axis_id)] = _int_attr(axis_telem, "device_tick", 0)
    return ticks


def extract_axis_estates(snap: object, axis_ids: Sequence[str]) -> dict[str, str]:
    word_by_axis = _mapping_attr(snap, "axis_estop_status_word")
    estates: dict[str, str] = {}
    for axis_id in axis_ids:
        raw_word = _mapping_value(word_by_axis, axis_id)
        if raw_word is None:
            continue
        word = _coerce_int(raw_word)
        if word is None:
            continue
        try:
            estates[str(axis_id)] = str(estate_from_word(word)).upper()
        except Exception:
            continue
    return estates


def extract_axis_positions(snap: object, axis_ids: Sequence[str]) -> dict[str, float]:
    axes = _mapping_attr(snap, "axes")
    positions: dict[str, float] = {}
    for axis_id in axis_ids:
        axis_telem = _mapping_value(axes, axis_id)
        if axis_telem is None:
            continue
        positions[str(axis_id)] = _float_attr(axis_telem, "pos", 0.0)
    return positions


def extract_axis_velocities(snap: object, axis_ids: Sequence[str]) -> dict[str, float]:
    axes = _mapping_attr(snap, "axes")
    velocities: dict[str, float] = {}
    for axis_id in axis_ids:
        axis_telem = _mapping_value(axes, axis_id)
        if axis_telem is None:
            continue
        velocities[str(axis_id)] = _float_attr(axis_telem, "vel", 0.0)
    return velocities


def extract_axis_owner(snap: object, axis_id: str) -> str:
    densis = _mapping_attr(snap, "densis")
    densi = _mapping_value(densis, axis_id)
    if densi is None:
        return ""
    densi_map = _as_str_object_mapping(densi)
    if densi_map:
        claimed = str(_mapping_value(densi_map, "claimed_by_hip") or "").strip()
        owner = str(_mapping_value(densi_map, "owner") or "").strip()
        return claimed or owner
    return _text_attr(densi, "claimed_by_hip") or _text_attr(densi, "owner")


def extract_axis_param_value(snap: object, axis_id: str, name: str) -> float | None:
    axis_params = _mapping_attr(snap, "axis_params")
    params = _mapping_value(axis_params, axis_id)
    if params is not None:
        params_map = _as_str_object_mapping(params)
        if params_map:
            raw = _mapping_value(params_map, name)
        else:
            raw = getattr(params, name, None)
        if raw is not None:
            value = _coerce_float(raw)
            if value is not None:
                return value

    params_top = _mapping_attr(snap, "params")
    raw_top = _mapping_value(params_top, name)
    if raw_top is None:
        return None
    return _coerce_float(raw_top)


def extract_axis_param_commit_status(snap: object, axis_id: str) -> str:
    statuses = _mapping_attr(snap, "axis_param_commit_status")
    raw = _mapping_value(statuses, axis_id)
    raw_map = _as_str_object_mapping(raw)
    if raw_map:
        status = str(_mapping_value(raw_map, "status") or _mapping_value(raw_map, "state") or "")
        if status:
            return status
    elif raw is not None:
        status = str(raw or "")
        if status:
            return status

    return _text_attr(snap, "param_commit_status")
