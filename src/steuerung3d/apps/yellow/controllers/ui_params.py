# src/steuerung3d/apps/yellow/controllers/ui_params.py
"""Parameter UI helpers shared by HiP and DenSi.

Why this exists:
- Keep param rendering consistent across panels (formatting + signal blocking).
- Reduce copy/paste drift between HiP and DenSi controllers.

These helpers are intentionally conservative:
- best-effort (never raise)
- diff-first (avoid churn)
- optionally skip focused edits (don't fight the operator)
"""

from __future__ import annotations

from typing import Any, Callable, Mapping


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

    # Late import keeps this helper usable in unit tests without Qt.
    try:
        from .ui_update import set_text  # type: ignore
    except Exception:
        return

    for grp, mapping in param_widgets.items():
        if freeze_group and str(grp) == str(freeze_group):
            continue
        for key, obj_name in mapping.items():
            if key not in params:
                continue
            le = None
            try:
                le = find_line_edit(obj_name)
            except Exception:
                le = None
            if le is None:
                continue

            try:
                if skip_focused and bool(getattr(le, "hasFocus")()):
                    continue
            except Exception:
                pass

            txt = param_value_to_text(params.get(key))
            try:
                if str(le.text()) == txt:
                    continue
            except Exception:
                pass

            if block_signals:
                try:
                    was = le.blockSignals(True)
                except Exception:
                    was = None
                set_text(le, txt)
                if was is not None:
                    try:
                        le.blockSignals(was)
                    except Exception:
                        pass
            else:
                set_text(le, txt)


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
    # Late import keeps this helper usable in unit tests without Qt.
    try:
        from .ui_update import set_text  # type: ignore
    except Exception:
        return False

    obj_name: str | None = None
    for _grp, mapping in param_widgets.items():
        if key in mapping:
            obj_name = str(mapping[key])
            break
    if not obj_name:
        return False

    try:
        le = find_line_edit(obj_name)
    except Exception:
        le = None
    if le is None:
        return False

    txt = param_value_to_text(value)
    try:
        if str(le.text()) == txt:
            return True
    except Exception:
        pass

    if block_signals:
        try:
            was = le.blockSignals(True)
        except Exception:
            was = None
        set_text(le, txt)
        if was is not None:
            try:
                le.blockSignals(was)
            except Exception:
                pass
    else:
        set_text(le, txt)

    return True
