from __future__ import annotations

from typing import Any, cast

import pytest

PySide6 = pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from steuerung3d.apps.supervisor.gui.window import (
    DISPLAY_SLIDER_MAX,
    LOAD_BAR_MAX_PCT,
    SupervisorWindow,
)


def test_slider_value_for_range_uses_user_limits() -> None:
    assert SupervisorWindow._slider_value_for_range(value=-20.0, minimum=-20.0, maximum=80.0) == 0
    assert (
        SupervisorWindow._slider_value_for_range(value=80.0, minimum=-20.0, maximum=80.0)
        == DISPLAY_SLIDER_MAX
    )
    assert SupervisorWindow._slider_value_for_range(value=30.0, minimum=-20.0, maximum=80.0) == 500


def test_slider_value_for_range_handles_degenerate_limits() -> None:
    center = SupervisorWindow._slider_value_for_range(value=5.0, minimum=5.0, maximum=5.0)
    assert center == DISPLAY_SLIDER_MAX // 2


def test_posdiff_formatter_uses_centimeters_with_precision() -> None:
    assert SupervisorWindow._format_posdiff_cm(0.03125) == "Δ 3.12 cm"


def test_load_bar_max_matches_supervisor_ui_target() -> None:
    assert LOAD_BAR_MAX_PCT == 170.0


def test_axis_table_content_height_tracks_row_count() -> None:
    app = QApplication.instance() or QApplication([])
    window = SupervisorWindow()
    zero_height = window._axis_table_content_height_for_rows(0)
    three_height = window._axis_table_content_height_for_rows(3)
    row_height = int(cast(Any, window.table.verticalHeader()).defaultSectionSize())

    assert three_height > zero_height
    assert three_height - zero_height == 3 * row_height

    window.close()
    _ = app
