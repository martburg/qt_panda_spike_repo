from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from steuerung3d.config.toml_loader import load_toml


@dataclass(frozen=True)
class InputdSimStepConfig:
    name: str
    hold_s: float
    ramp_s: float
    axis_targets: Mapping[int, float]
    button_targets: Mapping[int, bool]


@dataclass(frozen=True)
class InputdSimScenarioConfig:
    axis_aliases: Mapping[str, int]
    button_aliases: Mapping[str, int]
    steps: tuple[InputdSimStepConfig, ...]


@dataclass(frozen=True)
class InputdSimConfig:
    out_addr: tuple[str, int]
    control_in_addr: tuple[str, int] | None
    tick_hz: float
    num_axes: int
    num_buttons: int
    default_axis: float
    default_button: bool
    src: str
    autostart: bool
    scenario_path: Path
    scenario: InputdSimScenarioConfig


@dataclass(frozen=True)
class PreparedInputdSimStep:
    name: str
    hold_s: float
    ramp_s: float
    start_axes: tuple[float, ...]
    target_axes: tuple[float, ...]
    target_buttons: tuple[int, ...]


@dataclass(frozen=True)
class PreparedInputdSimScenario:
    initial_axes: tuple[float, ...]
    initial_buttons: tuple[int, ...]
    steps: tuple[PreparedInputdSimStep, ...]


@dataclass(frozen=True)
class InputdSimSample:
    axes: tuple[float, ...]
    buttons: tuple[int, ...]
    step_name: str
    active: bool


def _hostport(value: str) -> tuple[str, int]:
    host, port = value.rsplit(":", 1)
    return host.strip(), int(port)


def _as_table(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        return {}
    mapping = cast(Mapping[object, object], value)
    return {str(k): v for k, v in mapping.items()}


def _as_list(value: object) -> list[object]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return list(cast(Sequence[object], value))
    return []


def _as_bool(value: object, *, default: bool = False) -> bool:
    if value is None:
        return default
    return bool(value)


def _as_float(value: object, *, field_name: str, default: float) -> float:
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError as exc:
            raise ValueError(f"invalid float for {field_name}: {value!r}") from exc
    return float(default)


def _as_int(value: object, *, field_name: str, default: int) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError as exc:
            raise ValueError(f"invalid integer for {field_name}: {value!r}") from exc
    return int(default)


def _normalize_alias_map(
    raw: Mapping[str, object],
    *,
    max_index: int,
    field_name: str,
) -> dict[str, int]:
    out: dict[str, int] = {}
    for alias, raw_index in raw.items():
        name = str(alias).strip()
        if not name:
            raise ValueError(f"empty alias name in {field_name}")
        index = _as_int(raw_index, field_name=f"{field_name}.{name}", default=-1)
        if index < 0 or index >= max_index:
            raise ValueError(
                f"{field_name}.{name} index out of range: {index} not in [0, {max_index - 1}]"
            )
        out[name] = index
    return out


def _resolve_index(
    key: str,
    *,
    aliases: Mapping[str, int],
    max_index: int,
    field_name: str,
) -> int:
    token = str(key).strip()
    if token in aliases:
        index = int(aliases[token])
    else:
        try:
            index = int(token)
        except ValueError as exc:
            raise ValueError(f"unknown {field_name} target: {token!r}") from exc
    if index < 0 or index >= max_index:
        raise ValueError(f"{field_name} index out of range: {index} not in [0, {max_index - 1}]")
    return index


def _parse_axis_targets(
    raw: Mapping[str, object],
    *,
    aliases: Mapping[str, int],
    num_axes: int,
) -> dict[int, float]:
    out: dict[int, float] = {}
    for raw_key, raw_value in raw.items():
        index = _resolve_index(str(raw_key), aliases=aliases, max_index=num_axes, field_name="axes")
        value = _as_float(raw_value, field_name=f"axes.{raw_key}", default=0.0)
        if value < -1.0 or value > 1.0:
            raise ValueError(f"axes.{raw_key} out of range: {value} not in [-1.0, 1.0]")
        out[index] = float(value)
    return out


def _parse_button_targets(
    raw: Mapping[str, object],
    *,
    aliases: Mapping[str, int],
    num_buttons: int,
) -> dict[int, bool]:
    out: dict[int, bool] = {}
    for raw_key, raw_value in raw.items():
        index = _resolve_index(
            str(raw_key), aliases=aliases, max_index=num_buttons, field_name="buttons"
        )
        out[index] = bool(raw_value)
    return out


def _load_scenario(path: Path, *, num_axes: int, num_buttons: int) -> InputdSimScenarioConfig:
    raw = _as_table(load_toml(path))
    aliases_tbl = _as_table(raw.get("aliases", {}))
    axis_aliases = _normalize_alias_map(
        _as_table(aliases_tbl.get("axes", {})),
        max_index=num_axes,
        field_name="aliases.axes",
    )
    button_aliases = _normalize_alias_map(
        _as_table(aliases_tbl.get("buttons", {})),
        max_index=num_buttons,
        field_name="aliases.buttons",
    )

    steps_raw = _as_list(raw.get("steps", []))
    steps: list[InputdSimStepConfig] = []
    for idx, item in enumerate(steps_raw):
        tbl = _as_table(item)
        name = str(tbl.get("name") or f"step_{idx + 1}")
        hold_s = _as_float(tbl.get("hold_s", 0.0), field_name=f"steps[{idx}].hold_s", default=0.0)
        ramp_s = _as_float(tbl.get("ramp_s", 0.0), field_name=f"steps[{idx}].ramp_s", default=0.0)
        if hold_s < 0.0:
            raise ValueError(f"steps[{idx}].hold_s must be >= 0")
        if ramp_s < 0.0:
            raise ValueError(f"steps[{idx}].ramp_s must be >= 0")
        axis_targets = _parse_axis_targets(
            _as_table(tbl.get("axes", {})), aliases=axis_aliases, num_axes=num_axes
        )
        button_targets = _parse_button_targets(
            _as_table(tbl.get("buttons", {})), aliases=button_aliases, num_buttons=num_buttons
        )
        steps.append(
            InputdSimStepConfig(
                name=name,
                hold_s=float(hold_s),
                ramp_s=float(ramp_s),
                axis_targets=dict(axis_targets),
                button_targets=dict(button_targets),
            )
        )

    return InputdSimScenarioConfig(
        axis_aliases=dict(axis_aliases),
        button_aliases=dict(button_aliases),
        steps=tuple(steps),
    )


def load_inputd_sim_config(path: Path) -> InputdSimConfig:
    raw = _as_table(load_toml(path))
    io = _as_table(raw.get("io", {}))
    control = _as_table(raw.get("control", {}))
    input_tbl = _as_table(raw.get("input", {}))
    scenario_tbl = _as_table(raw.get("scenario", {}))

    out_addr = _hostport(str(io.get("out", "127.0.0.1:50100")))
    tick_hz = _as_float(io.get("tick_hz", 60.0), field_name="io.tick_hz", default=60.0)
    num_axes = _as_int(input_tbl.get("num_axes", 8), field_name="input.num_axes", default=8)
    num_buttons = _as_int(
        input_tbl.get("num_buttons", 16), field_name="input.num_buttons", default=16
    )
    if num_axes <= 0:
        raise ValueError("input.num_axes must be > 0")
    if num_buttons <= 0:
        raise ValueError("input.num_buttons must be > 0")

    default_axis = _as_float(
        input_tbl.get("default_axis", 0.0),
        field_name="input.default_axis",
        default=0.0,
    )
    if default_axis < -1.0 or default_axis > 1.0:
        raise ValueError("input.default_axis must be within [-1.0, 1.0]")
    default_button = _as_bool(input_tbl.get("default_button", False), default=False)
    src = str(input_tbl.get("src", "inputd_sim") or "inputd_sim")

    raw_control_addr = str(control.get("bind", "") or "").strip()
    control_in_addr = _hostport(raw_control_addr) if raw_control_addr else None
    autostart = _as_bool(control.get("autostart", False), default=False)

    scenario_rel = str(scenario_tbl.get("path", "") or "").strip()
    if not scenario_rel:
        raise ValueError("scenario.path is required")
    scenario_path = Path(scenario_rel)
    if not scenario_path.is_absolute():
        scenario_path = (path.parent / scenario_path).resolve()
    scenario = _load_scenario(scenario_path, num_axes=num_axes, num_buttons=num_buttons)

    return InputdSimConfig(
        out_addr=out_addr,
        control_in_addr=control_in_addr,
        tick_hz=float(tick_hz),
        num_axes=int(num_axes),
        num_buttons=int(num_buttons),
        default_axis=float(default_axis),
        default_button=bool(default_button),
        src=src,
        autostart=bool(autostart),
        scenario_path=scenario_path,
        scenario=scenario,
    )


def prepare_scenario(config: InputdSimConfig) -> PreparedInputdSimScenario:
    current_axes = [float(config.default_axis)] * int(config.num_axes)
    current_buttons = [1 if bool(config.default_button) else 0] * int(config.num_buttons)
    initial_axes = tuple(current_axes)
    initial_buttons = tuple(current_buttons)
    steps: list[PreparedInputdSimStep] = []

    for step in config.scenario.steps:
        start_axes = tuple(current_axes)
        target_axes = list(current_axes)
        target_buttons = list(current_buttons)
        for index, value in step.axis_targets.items():
            target_axes[int(index)] = float(value)
        for index, value in step.button_targets.items():
            target_buttons[int(index)] = 1 if bool(value) else 0
        steps.append(
            PreparedInputdSimStep(
                name=step.name,
                hold_s=float(step.hold_s),
                ramp_s=float(step.ramp_s),
                start_axes=start_axes,
                target_axes=tuple(target_axes),
                target_buttons=tuple(target_buttons),
            )
        )
        current_axes = target_axes
        current_buttons = target_buttons

    return PreparedInputdSimScenario(
        initial_axes=initial_axes,
        initial_buttons=initial_buttons,
        steps=tuple(steps),
    )


def interpolate_axes(
    start_axes: Sequence[float],
    target_axes: Sequence[float],
    *,
    elapsed_s: float,
    ramp_s: float,
) -> tuple[float, ...]:
    if ramp_s <= 0.0:
        return tuple(float(v) for v in target_axes)
    ratio = max(0.0, min(1.0, float(elapsed_s) / float(ramp_s)))
    return tuple(
        float(start) + (float(target) - float(start)) * ratio
        for start, target in zip(start_axes, target_axes, strict=False)
    )
