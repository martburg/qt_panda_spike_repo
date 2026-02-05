"""Stack (multi-process) boot configuration.

This module defines a small, versionable representation of the *boot stack*.

Design goals:
- Keep the current setup_stack behavior (logs per process, birds-eye, crash tail),
  but make *what we start* configurable.
- Make profiles portable (TOML), with per-axis fanout.
- Keep the runtime safe and deterministic: validate ports, expand templates, then run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional


FanoutMode = Literal["single", "per_axis"]


@dataclass(frozen=True)
class ServiceSpec:
    """A service to start as a subprocess."""

    enabled: bool = True
    module: str = ""  # python -m <module>
    mode: FanoutMode = "single"
    # Optional: start multiple identical instances ("pool") of this service.
    # If set to an int, starts that many processes named <key>-1..<key>-N.
    # If set to the string "auto", StackRuntime may choose a sensible count
    # based on the current inventory (SIM vs REAL).
    count: Any = None
    args: List[Any] = field(default_factory=list)
    config: Optional[str] = None  # if set, becomes --config <path>
    env: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class StackSpec:
    """Fully parsed stack profile."""

    name: str
    base_dir: Path

    # High-level rig: in SIM this is the expected axes list (spawns sims).
    # In REAL this may be empty; the runtime discovers devices from telemetry.
    axes: List[str]
    rig: Dict[str, Any]
    net: Dict[str, Any]

    # Services by key (core, hip, densi, inputd, joy2intent, ...)
    services: Dict[str, ServiceSpec]


@dataclass(frozen=True)
class ProcessSpec:
    """A concrete subprocess to launch."""

    name: str
    argv: List[str]
    log_path: Path
    env: Dict[str, str] = field(default_factory=dict)
    creationflags: int = 0
