from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Protocol, cast


class _TomlModule(Protocol):
    def loads(self, s: str, /) -> object: ...


try:
    import tomllib as _toml_module  # py3.11+
except ModuleNotFoundError:  # pragma: no cover
    import tomli as _toml_module  # type: ignore

tomllib = cast(_TomlModule, _toml_module)


def _as_table(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        return {}
    mapping = cast(Mapping[object, object], value)
    return {str(k): v for k, v in mapping.items()}


def _as_optional_int(value: object) -> Optional[int]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.strip())
        except Exception:
            return None
    return None


def _as_optional_axes(value: object) -> Optional[Sequence[str]]:
    if value is None:
        return None
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError("log_viewer config: [view].axes must be a list of strings")
    return [str(x) for x in cast(Sequence[object], value)]


@dataclass(frozen=True)
class LogViewerView:
    from_tick: Optional[int] = None
    to_tick: Optional[int] = None
    every: Optional[int] = None
    axes: Optional[Sequence[str]] = None
    show_pos: bool = True


@dataclass(frozen=True)
class LogViewerConfig:
    view: LogViewerView = LogViewerView()


def load_log_viewer_config(path: Path) -> LogViewerConfig:
    # Config is optional; if missing, use defaults.
    if not path.exists():
        return LogViewerConfig()

    data = _as_table(tomllib.loads(path.read_text(encoding="utf-8")))
    view = _as_table(data.get("view", {}))

    return LogViewerConfig(
        view=LogViewerView(
            from_tick=_as_optional_int(view.get("from_tick")),
            to_tick=_as_optional_int(view.get("to_tick")),
            every=_as_optional_int(view.get("every")),
            axes=_as_optional_axes(view.get("axes")),
            show_pos=bool(view.get("show_pos", True)),
        )
    )
