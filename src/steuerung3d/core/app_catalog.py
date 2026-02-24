"""App catalog for docs, tooling, and safe defaults.

This is intentionally lightweight and has **no runtime behavior**. It exists so
Docs and automation can reliably distinguish between supported entrypoints and
kept-for-compatibility modules.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class AppInfo:
    module: str
    kind: str  # "supported" | "obsolete"
    summary: str


APPS: Dict[str, AppInfo] = {
    # Supported stack components
    "core_udp_service": AppInfo(
        module="steuerung3d.apps.core_udp_service",
        kind="supported",
        summary="Canonical core service used by stack profiles (e.g. 1dev_sim).",
    ),
    "hi_p": AppInfo(
        module="steuerung3d.apps.hi_p",
        kind="supported",
        summary="Human Intent Parser (UI/controller).",
    ),
    "den_si": AppInfo(
        module="steuerung3d.apps.den_si",
        kind="supported",
        summary="DenSi device endpoint simulator.",
    ),
    "joy2intent": AppInfo(
        module="steuerung3d.apps.joy2intent",
        kind="supported",
        summary="Joystick input -> intents bridge.",
    ),
    "inputd": AppInfo(
        module="steuerung3d.apps.inputd",
        kind="supported",
        summary="Input daemon (keyboard/misc sources).",
    ),

    # Kept for compatibility / reference only
    "core_service": AppInfo(
        module="steuerung3d.apps.core_service",
        kind="obsolete",
        summary="Older core runner; superseded by core_udp_service + StackSpec profiles.",
    ),
    "plc_twincat_legacy_edge": AppInfo(
        module="steuerung3d.apps.plc_twincat_legacy_edge",
        kind="obsolete",
        summary="Legacy TwinCAT UDP edge adapter (kept for field rigs / reference).",
    ),
}


def supported_modules() -> Dict[str, str]:
    """Return mapping of app key -> module for supported apps."""

    return {k: v.module for k, v in APPS.items() if v.kind == "supported"}


def obsolete_modules() -> Dict[str, str]:
    """Return mapping of app key -> module for obsolete apps."""

    return {k: v.module for k, v in APPS.items() if v.kind == "obsolete"}
