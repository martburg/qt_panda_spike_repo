# src/steuerung3d/apps/yellow/qtutil/ui_params.py
"""Parameter UI helpers shared by Hip and DenSi.

Why this exists:
- Keep param rendering consistent across panels (formatting + signal blocking).
- Reduce copy/paste drift between Hip and DenSi controllers.

These helpers are intentionally conservative:
- best-effort (never raise)
- diff-first (avoid churn)
- optionally skip focused edits (don't fight the operator)
"""

from __future__ import annotations

from typing import Any, Callable, Mapping

from .ui_update import blocked_signals, set_text


def param_value_to_text(val: Any) -> str:
    """Format a parameter value for a QLineEdit.

    Policy:
    - numbers use `:g` (compact, stable)
    - None becomes empty
    - everything else uses str()
    """
    try:
        if val is None:
            return ""
        if isinstance(val, bool):
            # Avoid bool being treated as int.
            return "1" if val else "0"
        if isinstance(val, (int, float)):
            return f"{float(val):g}"
        return str(val)
    except Exception:
        return ""


def _find_param_line_edit(object_name: str, find_line_edit: Callable[[str], Any]) -> Any:
    try:
        return find_line_edit(object_name)
    except Exception:
        return None


def _write_line_edit_text(
    line_edit: Any,
    text: str,
    *,
    skip_focused: bool = False,
    block_signals_enabled: bool = True,
) -> bool:
    """Write QLineEdit text using the shared diff-first + signal-blocking policy.

    Returns True when the widget was a viable target, even if no text change was
    needed. Returns False only when no write should occur at all.
    """
    if line_edit is None:
        return False

    try:
        if skip_focused and bool(line_edit.hasFocus()):
            return False
    except Exception:
        pass

    try:
        if str(line_edit.text()) == text:
            return True
    except Exception:
        pass

    with blocked_signals(line_edit, enabled=block_signals_enabled):
        set_text(line_edit, text)
    return True


def apply_param_values_to_line_edits(
    params: Mapping[str, Any],
    param_widgets: Mapping[str, Mapping[str, str]],
    find_line_edit: Callable[[str], Any],
    *,
    freeze_group: str = "",
    skip_focused: bool = True,
    block_signals: bool = True,
) -> None:
    """Apply parameter values to QLineEdits declared in PARAM_WIDGETS.

    - `param_widgets` is usually yellow_maps.PARAM_WIDGETS
    - `find_line_edit(object_name)` must return a QLineEdit or None
    """
    if not params:
        return

    for grp, mapping in param_widgets.items():
        if freeze_group and str(grp) == str(freeze_group):
            continue
        for key, obj_name in mapping.items():
            if key not in params:
                continue
            le = _find_param_line_edit(obj_name, find_line_edit)
            if le is None:
                continue
            _write_line_edit_text(
                le,
                param_value_to_text(params.get(key)),
                skip_focused=bool(skip_focused),
                block_signals_enabled=bool(block_signals),
            )


def set_single_param_in_ui(
    key: str,
    value: Any,
    param_widgets: Mapping[str, Mapping[str, str]],
    find_line_edit: Callable[[str], Any],
    *,
    block_signals: bool = True,
) -> bool:
    """Set a single parameter value in the UI if a widget mapping exists.

    Returns True if a matching widget was found (even if the text was unchanged).
    """
    obj_name = next(
        (str(mapping[key]) for mapping in param_widgets.values() if key in mapping),
        None,
    )
    if not obj_name:
        return False

    le = _find_param_line_edit(obj_name, find_line_edit)
    return _write_line_edit_text(
        le,
        param_value_to_text(value),
        block_signals_enabled=bool(block_signals),
    )
