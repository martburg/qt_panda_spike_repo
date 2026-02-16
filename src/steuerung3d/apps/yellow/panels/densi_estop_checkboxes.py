"""DenSi E-Stop checkbox discovery / wiring / sync.

North refactor goal:
  - Keep DenSiController free of widget-walking boilerplate.
  - Preserve semantics: same keys, same init values, same block-signals sync.

This module is intentionally *thin*: it does not implement DenSi's E-Stop
state machine or injection policy. It only connects UI checkboxes to a
controller callback.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PySide6.QtWidgets import QCheckBox

from steuerung3d.protocol.estop_bits import decode_estop_word, iter_specs


@dataclass(frozen=True)
class DenSiEstopCheckboxBindings:
    """Resolved checkboxes by E-Stop key."""

    by_key: dict[str, QCheckBox]


def discover_densi_estop_checkboxes(*, get_checkbox: Callable[[str], QCheckBox | None]) -> DenSiEstopCheckboxBindings:
    """Discover checkboxes declared in ESTOP_SPECS.

    get_checkbox(object_name) should return a checkbox or None.
    """

    by_key: dict[str, QCheckBox] = {}
    for spec in iter_specs():
        if not spec.checkbox:
            continue
        cb = None
        try:
            cb = get_checkbox(spec.checkbox)
        except Exception:
            cb = None
        if cb is None:
            continue
        by_key[str(spec.key)] = cb
    return DenSiEstopCheckboxBindings(by_key=by_key)


def init_densi_estop_checkboxes(
    *,
    bindings: DenSiEstopCheckboxBindings,
    estop_word: int,
    set_checked: Callable[[QCheckBox, bool], None],
    set_enabled: Callable[[QCheckBox, bool], None],
    readonly_keys: set[str] | None = None,
) -> None:
    """Initialize checkboxes from an E-Stop word.

    readonly_keys: keys that should be disabled (e.g. reset_able).
    """

    ro = readonly_keys or set()
    bits = decode_estop_word(int(estop_word))
    for key, cb in bindings.by_key.items():
        try:
            set_checked(cb, bool(bits.get(key, False)))
        except Exception:
            pass
        try:
            set_enabled(cb, key not in ro)
        except Exception:
            pass


def sync_densi_estop_checkboxes(
    *,
    bindings: DenSiEstopCheckboxBindings,
    estop_word: int,
    set_checked: Callable[[QCheckBox, bool], None],
) -> None:
    """Sync checkbox states from an E-Stop word (block signals upstream)."""

    bits = decode_estop_word(int(estop_word))
    for key, cb in bindings.by_key.items():
        try:
            set_checked(cb, bool(bits.get(key, False)))
        except Exception:
            pass


def wire_densi_estop_checkboxes(*, bindings: DenSiEstopCheckboxBindings, on_toggled: Callable[[str, bool], None]) -> None:
    """Connect checkbox toggles to a controller callback."""

    for key, cb in bindings.by_key.items():
        try:
            cb.toggled.connect(lambda checked, _k=key: on_toggled(_k, bool(checked)))
        except Exception:
            continue
