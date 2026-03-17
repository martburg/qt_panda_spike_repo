from __future__ import annotations

from steuerung3d.apps.yellow.qtutil.ui_params import (
    apply_param_values_to_line_edits,
    set_single_param_in_ui,
)
from steuerung3d.apps.yellow.qtutil.ui_update import blocked_signals, set_checked


class _FakeLineEdit:
    def __init__(self, text: str = "", *, focused: bool = False) -> None:
        self._text = text
        self._focused = focused
        self.signal_log: list[bool] = []

    def text(self) -> str:
        return self._text

    def setText(self, text: str) -> None:
        self._text = text

    def hasFocus(self) -> bool:
        return self._focused

    def blockSignals(self, block: bool) -> bool:
        self.signal_log.append(block)
        return False


class _FakeCheckbox:
    def __init__(self, checked: bool = False) -> None:
        self._checked = checked
        self.signal_log: list[bool] = []

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool) -> None:
        self._checked = checked

    def blockSignals(self, block: bool) -> bool:
        self.signal_log.append(block)
        return False


def test_blocked_signals_restores_prior_state() -> None:
    widget = _FakeLineEdit()
    with blocked_signals(widget):
        widget.setText("x")
    assert widget.text() == "x"
    assert widget.signal_log == [True, False]


def test_set_checked_uses_shared_signal_blocking() -> None:
    checkbox = _FakeCheckbox()
    set_checked(checkbox, True, block_signals=True)
    assert checkbox.isChecked() is True
    assert checkbox.signal_log == [True, False]


def test_apply_param_values_to_line_edits_skips_focused_field() -> None:
    widgets = {
        "grp": {
            "a": "le_a",
            "b": "le_b",
        }
    }
    le_a = _FakeLineEdit("1", focused=True)
    le_b = _FakeLineEdit("2")
    lookup = {"le_a": le_a, "le_b": le_b}

    apply_param_values_to_line_edits(
        {"a": 3.0, "b": 4.0},
        widgets,
        lambda name: lookup.get(name),
        skip_focused=True,
        block_signals=True,
    )

    assert le_a.text() == "1"
    assert le_a.signal_log == []
    assert le_b.text() == "4"
    assert le_b.signal_log == [True, False]


def test_set_single_param_in_ui_returns_true_for_unchanged_text() -> None:
    widgets = {"grp": {"a": "le_a"}}
    le_a = _FakeLineEdit("5")

    found = set_single_param_in_ui(
        "a",
        5,
        widgets,
        lambda name: le_a if name == "le_a" else None,
    )

    assert found is True
    assert le_a.text() == "5"
    assert le_a.signal_log == []
