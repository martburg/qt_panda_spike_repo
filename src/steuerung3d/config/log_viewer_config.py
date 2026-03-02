from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

try:
    import tomllib  # py3.11+
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore


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

    data = tomllib.loads(path.read_text(encoding="utf-8"))
    view = data.get("view", {}) if isinstance(data, dict) else {}

    axes = view.get("axes")
    if axes is not None and not isinstance(axes, list):
        raise ValueError("log_viewer config: [view].axes must be a list of strings")

    return LogViewerConfig(
        view=LogViewerView(
            from_tick=view.get("from_tick"),
            to_tick=view.get("to_tick"),
            every=view.get("every"),
            axes=axes,
            show_pos=bool(view.get("show_pos", True)),
        )
    )
