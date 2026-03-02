"""Shared parameter widget helpers for Yellow (Qt-bound)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping

from PySide6.QtCore import QLocale
from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import QLineEdit, QWidget

from .ui_params import apply_param_values_to_line_edits
from .ui_update import set_enabled, set_state_property, set_text
from .widget_cache import WidgetCache


@dataclass
class ParamWidgetBinder:
    win: QWidget
    log: logging.Logger
    param_widgets: Mapping[str, Mapping[str, str]]
    limit_widgets: Mapping[str, str]
    cache: WidgetCache | None = None

    def __post_init__(self) -> None:
        if self.cache is None:
            self.cache = WidgetCache(self.win)

    def find_line_edit(self, object_name: str) -> QLineEdit | None:
        try:
            if self.cache is not None:
                return self.cache.line_edit(object_name)
        except Exception:
            pass
        w = self.win.findChild(QLineEdit, object_name)
        return w if isinstance(w, QLineEdit) else None

    def iter_param_line_edits(self) -> Iterable[tuple[str, str, str, QLineEdit]]:
        for grp, mapping in self.param_widgets.items():
            for key, obj_name in mapping.items():
                le = self.find_line_edit(obj_name)
                if le is None:
                    continue
                yield str(grp), str(key), str(obj_name), le

    def read_group_values(self, group: str) -> dict[str, float]:
        mapping = self.param_widgets.get(group, {})
        out: dict[str, float] = {}
        for key, obj_name in mapping.items():
            le = self.find_line_edit(obj_name)
            if le is None:
                continue
            try:
                out[key] = self._parse_float(le.text())
            except ValueError:
                self.log.warning("param parse failed: %s=%r", key, le.text())
        return out

    def read_all_values(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for _grp, mapping in self.param_widgets.items():
            for key, obj_name in mapping.items():
                le = self.find_line_edit(obj_name)
                if le is None:
                    continue
                try:
                    out[key] = self._parse_float(le.text())
                except ValueError:
                    continue
        return out

    def apply_param_values(
        self,
        params: Mapping[str, Any],
        *,
        freeze_group: str = "",
        skip_focused: bool = True,
        block_signals: bool = True,
    ) -> None:
        apply_param_values_to_line_edits(
            params,
            self.param_widgets,
            self.find_line_edit,
            freeze_group=str(freeze_group or ""),
            skip_focused=bool(skip_focused),
            block_signals=bool(block_signals),
        )

    def apply_limit_values(
        self,
        values: Mapping[str, float],
        *,
        format_value: Callable[[float], str],
        disable: bool = True,
    ) -> None:
        for key, obj_name in self.limit_widgets.items():
            if key not in values:
                continue
            le = self.find_line_edit(obj_name)
            if le is None:
                continue
            try:
                txt = format_value(float(values[key]))
            except Exception:
                txt = ""
            set_text(le, txt)
            if disable:
                try:
                    set_enabled(le, False)
                except Exception:
                    pass

    def init_param_inputs(self) -> None:
        loc = QLocale.system()
        for _grp, _key, _obj, le in self.iter_param_line_edits():
            set_state_property(le, "true", prop="paramField")
            val = QDoubleValidator(-1.0e12, 1.0e12, 6, le)
            val.setLocale(loc)
            val.setNotation(QDoubleValidator.Notation.StandardNotation)
            le.setValidator(val)

    @staticmethod
    def _parse_float(s: str) -> float:
        s = (s or "").strip()
        if not s:
            return 0.0
        s = s.replace(",", ".")
        return float(s)
