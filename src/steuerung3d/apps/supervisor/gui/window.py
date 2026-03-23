from __future__ import annotations

from typing import Any, cast

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from steuerung3d.rig.scene.two_axis_head_snapshot import SceneSnapshot

from ..models import AxisRow, SupervisorSnapshot
from ..row_estop_dots import ESTOP_GRID_COLUMNS, ESTOP_GRID_ROWS, SUPERVISOR_ESTOP_COLUMNS
from .viewport.selection_bridge import ViewportSelectionEvent, selection_summary_from_event
from .viewport.viewport_host import ViewportHost

DISPLAY_SLIDER_MAX = 1000
DISPLAY_SLIDER_CENTER = DISPLAY_SLIDER_MAX // 2
LOAD_BAR_MAX_PCT = 170.0
SYNC_FRAMES: tuple[str, ...] = ("◴", "◷", "◶", "◵")
DOT_SIZE_PX = 7
DOT_RED_STYLE = (
    f"min-width:{DOT_SIZE_PX}px; max-width:{DOT_SIZE_PX}px; "
    f"min-height:{DOT_SIZE_PX}px; max-height:{DOT_SIZE_PX}px; "
    "border-radius:4px; background-color:#cc3333; border:1px solid #992222;"
)
DOT_GREEN_STYLE = (
    f"min-width:{DOT_SIZE_PX}px; max-width:{DOT_SIZE_PX}px; "
    f"min-height:{DOT_SIZE_PX}px; max-height:{DOT_SIZE_PX}px; "
    "border-radius:4px; background-color:#33cc66; border:1px solid #2a9d4b;"
)
DOT_YELLOW_STYLE = (
    f"min-width:{DOT_SIZE_PX}px; max-width:{DOT_SIZE_PX}px; "
    f"min-height:{DOT_SIZE_PX}px; max-height:{DOT_SIZE_PX}px; "
    "border-radius:4px; background-color:#d6b84a; border:1px solid #9f8730;"
)

HEADERS: list[str] = [
    "axis",
    "sel",
    "diff",
    "E-Stop",
    "phase(state)",
    "pos",
    "vel",
    "load",
    "diag",
    "sync",
    "hip",
]

COL_AXIS = 0
COL_SELECTED = 1
COL_DIFF = 2
COL_ESTOP = 3
COL_PHASE = 4
COL_POS = 5
COL_VEL = 6
COL_LOAD = 7
COL_DIAG = 8
COL_SYNC = 9
COL_HIP = 10


class _TooltipDot(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)


class _EstopBlockWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._cells: list[_TooltipDot] = []


class _CaretSlider(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._minimum = 0
        self._maximum = DISPLAY_SLIDER_MAX
        self._value = DISPLAY_SLIDER_CENTER
        self.setMinimumHeight(16)

    def setRange(self, minimum: int, maximum: int) -> None:
        self._minimum = int(minimum)
        self._maximum = max(int(maximum), self._minimum + 1)
        self.update()

    def setValue(self, value: int) -> None:
        self._value = max(self._minimum, min(self._maximum, int(value)))
        self.update()

    def paintEvent(self, _event: object) -> None:  # pragma: no cover (Qt)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        width = max(1, self.width())
        height = max(1, self.height())
        left = 4
        right = max(left + 1, width - 4)
        line_y = max(2, int(height * 0.34))

        painter.setPen(QPen(QColor("#7a7a7a"), 1))
        painter.drawLine(left, line_y, right, line_y)

        span = max(1, self._maximum - self._minimum)
        normalized = (self._value - self._minimum) / span
        x_pos = left + int(round(normalized * (right - left)))
        caret_y = min(height - 2, line_y + 11)
        painter.setPen(QPen(QColor("#202020"), 1))
        painter.drawText(max(0, x_pos - 4), caret_y, "^")
        painter.end()


class _ValueSliderWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._min_label: QLabel | None = None
        self._value_label: QLabel | None = None
        self._max_label: QLabel | None = None
        self._value_slider: _CaretSlider | None = None


class _AxisCellWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._accent_top: QFrame | None = None
        self._accent_bottom: QFrame | None = None
        self._label: QLabel | None = None


class _PhaseBadgeWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._label: QLabel | None = None


class _SelectionCellWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._checkbox: QCheckBox | None = None


class _LoadBarWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._value_pct = 0.0
        self.setMinimumHeight(32)

    def set_value_pct(self, value_pct: float) -> None:
        self._value_pct = max(0.0, min(LOAD_BAR_MAX_PCT, float(value_pct)))
        self.update()

    def paintEvent(self, _event: object) -> None:  # pragma: no cover (Qt)
        painter = QPainter(self)
        try:
            qp = cast(Any, painter)
            width = max(1, self.width())
            height = max(1, self.height())
            rect_x = max(2, width // 2 - 4)
            rect_w = max(6, min(8, width - 4))
            rect_y = 2
            rect_h = max(8, height - 4)

            track_pen = QPen(QColor("#8a8f96"), 1)
            track_fill = QColor("#f2f4f6")
            qp.setPen(track_pen)
            qp.setBrush(track_fill)
            qp.drawRoundedRect(rect_x, rect_y, rect_w, rect_h, 2, 2)

            fill_ratio = max(0.0, min(1.0, self._value_pct / LOAD_BAR_MAX_PCT))
            fill_h = max(1, int(round(rect_h * fill_ratio)))
            fill_y = rect_y + rect_h - fill_h
            fill_color = QColor("#4aaf64")
            if self._value_pct > 150.0:
                fill_color = QColor("#d06a25")
            elif self._value_pct > 100.0:
                fill_color = QColor("#c6a63a")
            qp.setPen(QPen(fill_color, 1))
            qp.setBrush(fill_color)
            qp.drawRoundedRect(rect_x + 1, fill_y + 1, max(1, rect_w - 2), max(1, fill_h - 2), 1, 1)

            marker_ratio = 100.0 / LOAD_BAR_MAX_PCT
            marker_y = rect_y + rect_h - int(round(rect_h * marker_ratio))
            qp.setPen(QPen(QColor("#69727d"), 1))
            qp.drawLine(rect_x - 1, marker_y, rect_x + rect_w + 1, marker_y)
        finally:
            painter.end()


class _DiagCellWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._temp_label: QLabel | None = None
        self._posdiff_label: QLabel | None = None


class _SyncSpinnerWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._label: QLabel | None = None


class SupervisorWindow(QMainWindow):
    reset_estop_clicked = Signal()
    estart_clicked = Signal()
    resync_clicked = Signal()
    recover_clicked = Signal()
    chk_es_taster_changed = Signal(bool)
    pair_selected_changed = Signal(str, bool)
    unit_selected_changed = Signal(str, bool)
    open_hip_clicked = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Supervisor")
        root = QWidget(self)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(6, 6, 6, 6)
        root_layout.setSpacing(6)

        self.status_label = QLabel("System: NO PAIRS")
        root_layout.addWidget(self.status_label)

        toolbar = QHBoxLayout()
        self.btn_reset = QPushButton("Reset EStop")
        self.btn_estart = QPushButton("EStart")
        self.btn_resync = QPushButton("Resync")
        self.btn_recover = QPushButton("Recover")
        self.chk_taster = QCheckBox("chkEsTaster")
        toolbar.addWidget(self.btn_reset)
        toolbar.addWidget(self.btn_estart)
        toolbar.addWidget(self.btn_resync)
        toolbar.addWidget(self.btn_recover)
        toolbar.addWidget(self.chk_taster)
        toolbar.addStretch(1)
        root_layout.addLayout(toolbar)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(8)

        self.left_panel = self._make_side_panel(
            title="Components",
            body_text=(
                "Current slice keeps the shell/viewport split narrow. "
                "Two-axis head remains the only machine target."
            ),
        )
        body.addWidget(self.left_panel, 0)

        center = QWidget(root)
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(8)

        self.viewport_host = ViewportHost(center)
        center_layout.addWidget(self.viewport_host, 1)

        table_wrap = QFrame(center)
        table_wrap.setFrameShape(QFrame.Shape.StyledPanel)
        table_layout = QVBoxLayout(table_wrap)
        table_layout.setContentsMargins(4, 4, 4, 4)
        table_layout.setSpacing(4)
        table_title = QLabel("Supervisor Axis Table", table_wrap)
        table_title.setStyleSheet("font-weight: 600;")
        table_layout.addWidget(table_title)
        self._table_wrap = table_wrap
        self._table_title = table_title
        self.table = QTableWidget(0, len(HEADERS))
        self.table.setHorizontalHeaderLabels(HEADERS)
        qt_any = cast(Any, Qt)
        scrollbar_policy = qt_any.ScrollBarPolicy.ScrollBarAlwaysOff
        cast(Any, self.table).setVerticalScrollBarPolicy(scrollbar_policy)
        self._configure_column_widths()
        table_layout.addWidget(self.table)
        center_layout.addWidget(table_wrap)

        body.addWidget(center, 1)

        self.right_panel = self._make_side_panel(
            title="Selection / Diagnostics", body_text="No viewport selection"
        )
        body.addWidget(self.right_panel, 0)

        root_layout.addLayout(body, 1)
        self.setCentralWidget(root)
        self.setStyleSheet("QToolTip { font-size: 12pt; padding: 8px 10px; }")
        self.btn_reset.clicked.connect(self.reset_estop_clicked.emit)
        self.btn_estart.clicked.connect(self.estart_clicked.emit)
        self.btn_resync.clicked.connect(self.resync_clicked.emit)
        self.btn_recover.clicked.connect(self.recover_clicked.emit)
        self.chk_taster.toggled.connect(self.chk_es_taster_changed.emit)
        self.viewport_host.selection_changed.connect(self._on_viewport_selection_changed)
        self._updating = False
        self._sync_progress: dict[str, tuple[str, int]] = {}
        self._last_scene_snapshot: SceneSnapshot | None = None

    def apply_snapshot(self, snap: SupervisorSnapshot) -> None:
        self._updating = True
        try:
            self.setWindowTitle(str(snap.title))
            self.status_label.setText(str(snap.status_text))
            rows = list(snap.rows)
            locked = int(getattr(snap, "hip_open_total", 0) or 0) > 0
            vel_span = self._display_velocity_span(rows)
            self.btn_reset.setEnabled(not locked)
            self.btn_estart.setEnabled(not locked)
            self.btn_resync.setEnabled(not locked)
            self.chk_taster.setEnabled(not locked)
            if locked:
                self.chk_taster.blockSignals(True)
                self.chk_taster.setChecked(False)
                self.chk_taster.blockSignals(False)
            self.table.setRowCount(len(rows))
            active_units = {row.unit_id for row in rows}
            self._sync_progress = {
                unit_id: state
                for unit_id, state in self._sync_progress.items()
                if unit_id in active_units
            }
            for row_idx, row in enumerate(rows):
                self.table.setRowHeight(row_idx, 44)
                self._set_axis_cell(row=row_idx, axis_row=row)
                chk = self._selection_checkbox(row_idx)
                if chk is None:
                    cell = self._make_selection_checkbox_widget()
                    self.table.setCellWidget(row_idx, COL_SELECTED, cell)
                    chk = cell._checkbox
                    if chk is None:
                        raise RuntimeError("selection checkbox widget missing checkbox")
                    chk.toggled.connect(self._make_unit_selected_handler(row.unit_id))
                chk.blockSignals(True)
                chk.setChecked(bool(row.selected))
                chk.setEnabled(not locked)
                chk.blockSignals(False)
                self._set_text(row_idx, COL_DIFF, str(int(row.livetick_diff)))
                self._set_estop_block(row_idx=row_idx, row=row)
                self._set_phase_badge(row=row_idx, axis_row=row)
                pos_min, pos_max = self._position_limits(row)
                self._set_value_slider(
                    row=row_idx,
                    col=COL_POS,
                    value=float(row.pos),
                    slider_value=self._slider_value_for_range(
                        value=row.pos, minimum=pos_min, maximum=pos_max
                    ),
                    minimum=pos_min,
                    maximum=pos_max,
                )
                self._set_value_slider(
                    row=row_idx,
                    col=COL_VEL,
                    value=float(row.vel),
                    slider_value=self._slider_value_for_signed_display(row.vel, vel_span),
                    minimum=-vel_span,
                    maximum=vel_span,
                    show_minimum_label=False,
                )
                self._set_load_bar(row=row_idx, axis_row=row)
                self._set_diag_cell(row=row_idx, axis_row=row)
                self._set_sync_spinner(row=row_idx, axis_row=row)
                btn = self.table.cellWidget(row_idx, COL_HIP)
                if not isinstance(btn, QPushButton):
                    btn = QPushButton()
                    btn.clicked.connect(self._make_open_hip_handler(row.unit_id))
                    self.table.setCellWidget(row_idx, COL_HIP, btn)
                btn.setText(self._hip_button_text(int(row.hip_open_count)))
            while self.table.rowCount() > len(rows):
                self.table.removeRow(self.table.rowCount() - 1)
            self._fit_axis_table_height(len(rows))
        finally:
            self._updating = False

    def show_recover_placeholder(self) -> None:
        QMessageBox.information(self, "Recover", "Recover not implemented yet.")

    def apply_scene_snapshot(self, scene: SceneSnapshot | None) -> None:
        self._last_scene_snapshot = scene
        self.viewport_host.apply_scene_snapshot(scene)
        if scene is None:
            self._selection_body_label.setText("No viewport selection")
            return
        warning_text = ", ".join(scene.warnings) if scene.warnings else "none"
        self._selection_hint_label.setText(
            f"scene machine={scene.machine_id} | warnings={warning_text}"
        )

    def _on_viewport_selection_changed(self, event: ViewportSelectionEvent | None) -> None:
        state = selection_summary_from_event(event)
        self._selection_body_label.setText(state.summary_text)

    def _make_side_panel(self, *, title: str, body_text: str) -> QFrame:
        panel = QFrame(self)
        panel.setFrameShape(QFrame.Shape.StyledPanel)
        cast(Any, panel).setMinimumWidth(180)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        title_label = QLabel(title, panel)
        title_label.setStyleSheet("font-weight: 600;")
        body_label = QLabel(body_text, panel)
        cast(Any, body_label).setWordWrap(True)
        hint_label = QLabel("Stack-led shell; Panda viewport in center panel.", panel)
        cast(Any, hint_label).setWordWrap(True)
        hint_label.setStyleSheet("color: #66707d; font-size: 11px;")
        layout.addWidget(title_label)
        layout.addWidget(body_label)
        layout.addStretch(1)
        layout.addWidget(hint_label)
        if title.startswith("Selection"):
            self._selection_body_label = body_label
            self._selection_hint_label = hint_label
        return panel

    def _emit_unit_selected(self, unit_id: str, checked: bool) -> None:
        if self._updating:
            return
        normalized_unit_id = str(unit_id)
        normalized_checked = bool(checked)
        self.unit_selected_changed.emit(normalized_unit_id, normalized_checked)
        self.pair_selected_changed.emit(normalized_unit_id, normalized_checked)

    def _make_unit_selected_handler(self, unit_id: str):
        def _on_toggled(checked: bool) -> None:
            self._emit_unit_selected(unit_id, bool(checked))

        return _on_toggled

    def _make_open_hip_handler(self, unit_id: str):
        def _on_clicked(_checked: bool = False) -> None:
            self.open_hip_clicked.emit(unit_id)

        return _on_clicked

    @staticmethod
    def _hip_button_text(open_count: int) -> str:
        if int(open_count) <= 0:
            return "Open HiP"
        return f"Open HiP ({int(open_count)})"

    def _set_text(self, row: int, col: int, text: str) -> None:
        item = self.table.item(row, col)
        if item is None:
            item = QTableWidgetItem()
            if col != COL_AXIS:
                item.setTextAlignment(int(Qt.AlignmentFlag.AlignCenter))
            self.table.setItem(row, col, item)
        item.setText(text)

    def _set_axis_cell(self, *, row: int, axis_row: AxisRow) -> None:
        container = self.table.cellWidget(row, COL_AXIS)
        if not isinstance(container, _AxisCellWidget):
            container = self._make_axis_cell_widget()
            self.table.setCellWidget(row, COL_AXIS, container)
        label = container._label
        accent_top = container._accent_top
        accent_bottom = container._accent_bottom
        if label is not None:
            label.setText(axis_row.axis_id)
        densi_color = self._identity_color(axis_row.densi_id, family="densi")
        hip_color = self._identity_color(axis_row.hip_id, family="hip")
        if accent_top is not None:
            accent_top.setStyleSheet(
                f"QFrame {{ background-color: {densi_color}; border-top-left-radius: 3px; border-top-right-radius: 3px; }}"
            )
        if accent_bottom is not None:
            accent_bottom.setStyleSheet(
                f"QFrame {{ background-color: {hip_color}; border-bottom-right-radius: 3px; border-bottom-left-radius: 3px; }}"
            )
        container.setToolTip(
            f"axis={axis_row.axis_id} | densi={axis_row.densi_id or '-'} | hip={axis_row.hip_id or '-'}"
        )

    def _selection_checkbox(self, row: int) -> QCheckBox | None:
        cell = self.table.cellWidget(row, COL_SELECTED)
        if isinstance(cell, QCheckBox):
            return cell
        if isinstance(cell, _SelectionCellWidget):
            return cell._checkbox
        return None

    def _set_phase_badge(self, *, row: int, axis_row: AxisRow) -> None:
        container = self.table.cellWidget(row, COL_PHASE)
        if not isinstance(container, _PhaseBadgeWidget):
            container = self._make_phase_badge_widget()
            self.table.setCellWidget(row, COL_PHASE, container)
        label = container._label
        phase = axis_row.phase
        phase_bg, phase_border, phase_fg = self._phase_palette(phase)
        if label is not None:
            label.setText(phase.value)
            label.setStyleSheet(
                "QLabel {"
                f" background-color: {phase_bg};"
                f" color: {phase_fg};"
                f" border: 1px solid {phase_border};"
                " border-radius: 8px;"
                " padding: 2px 7px;"
                " font-weight: 600;"
                "}"
            )
        container.setToolTip(f"phase={phase.value}")

    @staticmethod
    def _make_phase_badge_widget() -> _PhaseBadgeWidget:
        container = _PhaseBadgeWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(2, 0, 2, 0)
        layout.setSpacing(0)

        label = QLabel("IDLE", container)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(label, 1)

        container._label = label
        return container

    @staticmethod
    def _make_axis_cell_widget() -> _AxisCellWidget:
        container = _AxisCellWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(2, 0, 2, 0)
        layout.setSpacing(5)

        accent = QWidget(container)
        accent.setFixedWidth(6)
        accent_layout = QVBoxLayout(accent)
        accent_layout.setContentsMargins(0, 1, 0, 1)
        accent_layout.setSpacing(0)
        accent_top = QFrame(accent)
        accent_bottom = QFrame(accent)
        accent_layout.addWidget(accent_top, 1)
        accent_layout.addWidget(accent_bottom, 1)

        label = QLabel("axis", container)
        label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

        layout.addWidget(accent)
        layout.addWidget(label, 1)

        container._accent_top = accent_top
        container._accent_bottom = accent_bottom
        container._label = label
        return container

    @staticmethod
    def _phase_palette(phase: object) -> tuple[str, str, str]:
        phase_name = str(getattr(phase, "value", phase)).upper()
        palette = {
            "ESTOP": ("#f7efbf", "#d7bc47", "#6d5600"),
            "IDLE": ("#ebedf0", "#b7bec8", "#38424d"),
            "ARMED": ("#e0ebfb", "#7ea4db", "#1f4f8f"),
            "READY": ("#dceff0", "#78b7ba", "#1f6367"),
            "LIVE": ("#dff2df", "#79b27a", "#1e5f2c"),
            "STALE": ("#f6ebcf", "#d0b16d", "#7d5b10"),
        }
        return palette.get(phase_name, ("#ebedf0", "#b7bec8", "#38424d"))

    @staticmethod
    def _identity_color(device_id: str, *, family: str) -> str:
        normalized = "".join(ch for ch in str(device_id).lower() if ch.isalnum())
        named = {
            "anton": "#c28a2e",
            "debby": "#4c87c8",
            "burt": "#5f9d63",
            "cecil": "#8a67c7",
        }
        for key, color in named.items():
            if key in normalized:
                return color
        palette = {
            "densi": ("#c28a2e", "#c05a45", "#76933c", "#7f6db0"),
            "hip": ("#4c87c8", "#3f9aa8", "#8a67c7", "#5470c6"),
        }
        choices = palette.get(family, palette["hip"])
        index = sum(ord(ch) for ch in normalized) % len(choices) if normalized else 0
        return choices[index]

    @staticmethod
    def _make_selection_checkbox_widget() -> _SelectionCellWidget:
        container = _SelectionCellWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        chk = QCheckBox(parent=container)
        chk.setText("")
        chk.setStyleSheet("QCheckBox { margin: 0px; padding: 0px; }")
        layout.addWidget(chk)
        container._checkbox = chk
        return container

    def _fit_axis_table_height(self, row_count: int) -> None:
        title_height = self._table_title.sizeHint().height()
        table_height = self._axis_table_content_height_for_rows(row_count)
        wrap_layout = cast(QVBoxLayout, self._table_wrap.layout())
        margins = cast(Any, wrap_layout).contentsMargins()
        frame_width = int(cast(Any, self._table_wrap).frameWidth())
        spacing = int(cast(Any, wrap_layout).spacing())
        wrap_height = (
            frame_width * 2
            + int(margins.top())
            + title_height
            + spacing
            + table_height
            + int(margins.bottom())
        )
        cast(Any, self.table).setFixedHeight(table_height)
        cast(Any, self._table_wrap).setFixedHeight(wrap_height)

    def _axis_table_content_height_for_rows(self, row_count: int) -> int:
        header_height = int(cast(Any, self.table).horizontalHeader().height())
        row_height = int(cast(Any, self.table.verticalHeader()).defaultSectionSize())
        rows_height = max(0, row_count) * row_height
        horizontal_scroll_bar = cast(Any, self.table).horizontalScrollBar()
        horizontal_scroll_height = (
            int(horizontal_scroll_bar.sizeHint().height())
            if horizontal_scroll_bar.isVisible()
            else 0
        )
        frame_width = int(cast(Any, self.table).frameWidth())
        return frame_width * 2 + header_height + rows_height + horizontal_scroll_height

    def _configure_column_widths(self) -> None:
        self.table.setColumnWidth(COL_AXIS, 118)
        self.table.setColumnWidth(COL_SELECTED, 30)
        self.table.setColumnWidth(COL_DIFF, 36)
        self.table.setColumnWidth(COL_ESTOP, 144)
        self.table.setColumnWidth(COL_PHASE, 102)
        self.table.setColumnWidth(COL_POS, 188)
        self.table.setColumnWidth(COL_VEL, 166)
        self.table.setColumnWidth(COL_LOAD, 26)
        self.table.setColumnWidth(COL_DIAG, 92)
        self.table.setColumnWidth(COL_SYNC, 34)
        self.table.setColumnWidth(COL_HIP, 110)
        self.table.verticalHeader().setDefaultSectionSize(44)

    def _set_estop_block(self, *, row_idx: int, row: AxisRow) -> None:
        container = self.table.cellWidget(row_idx, COL_ESTOP)
        if not isinstance(container, QWidget):
            container = self._make_estop_block_widget()
            self.table.setCellWidget(row_idx, COL_ESTOP, container)
        cells = container._cells if isinstance(container, _EstopBlockWidget) else None
        if cells is None:
            return
        states = tuple(row.estop_dots)
        for idx, column in enumerate(SUPERVISOR_ESTOP_COLUMNS):
            if idx >= len(cells):
                break
            dot = cells[idx]
            state = states[idx] if idx < len(states) else None
            label = column.header
            self._set_dot_state(dot, state=state, label=label)
            parent = dot.parentWidget()
            tooltip = label if label else ""
            if parent is not None:
                parent.setToolTip(tooltip)

    @staticmethod
    def _make_estop_block_widget() -> _EstopBlockWidget:
        container = _EstopBlockWidget()
        grid = QGridLayout(container)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(0)
        grid.setVerticalSpacing(0)
        cells: list[_TooltipDot] = []
        for row in range(ESTOP_GRID_ROWS):
            for col in range(ESTOP_GRID_COLUMNS):
                idx = row * ESTOP_GRID_COLUMNS + col
                column = SUPERVISOR_ESTOP_COLUMNS[idx]
                dot_wrap = QWidget(container)
                dot_wrap.setContentsMargins(0, 0, 0, 0)
                dot_wrap_layout = QHBoxLayout(dot_wrap)
                dot_wrap_layout.setContentsMargins(0, 0, 0, 0)
                dot_wrap_layout.setSpacing(0)
                dot_wrap_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                dot = _TooltipDot(dot_wrap)
                dot.setStyleSheet(DOT_YELLOW_STYLE)
                dot_wrap.setToolTip(column.header)
                if not column.header:
                    dot.setVisible(False)
                    dot_wrap.setToolTip("")
                dot_wrap_layout.addWidget(dot)
                grid.addWidget(dot_wrap, row, col)
                cells.append(dot)
        container._cells = cells
        return container

    @staticmethod
    def _set_dot_state(dot: _TooltipDot, *, state: bool | None, label: str) -> None:
        if state is None:
            dot.setStyleSheet(DOT_YELLOW_STYLE)
        elif bool(state):
            dot.setStyleSheet(DOT_GREEN_STYLE)
        else:
            dot.setStyleSheet(DOT_RED_STYLE)

    def _set_value_slider(
        self,
        *,
        row: int,
        col: int,
        value: float,
        slider_value: int,
        minimum: float,
        maximum: float,
        show_minimum_label: bool = True,
    ) -> None:
        container = self.table.cellWidget(row, col)
        if not isinstance(container, QWidget):
            container = self._make_value_slider_widget()
            self.table.setCellWidget(row, col, container)
        min_label = container._min_label if isinstance(container, _ValueSliderWidget) else None
        label = container._value_label if isinstance(container, _ValueSliderWidget) else None
        max_label = container._max_label if isinstance(container, _ValueSliderWidget) else None
        slider = container._value_slider if isinstance(container, _ValueSliderWidget) else None
        if min_label is not None:
            min_label.setText(f"{float(minimum):.3f}" if show_minimum_label else "")
        if label is not None:
            label.setText(f"{float(value):.3f}")
        if max_label is not None:
            max_label.setText(f"{float(maximum):.3f}")
        if slider is not None:
            slider.setValue(int(slider_value))
            if show_minimum_label:
                slider.setToolTip(
                    f"min {float(minimum):.3f} | value {float(value):.3f} | max {float(maximum):.3f}"
                )
            else:
                slider.setToolTip(f"value {float(value):.3f} | max {float(maximum):.3f}")

    @staticmethod
    def _make_value_slider_widget() -> _ValueSliderWidget:
        container = _ValueSliderWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(1, 0, 1, 0)
        layout.setSpacing(0)
        labels = QHBoxLayout()
        labels.setContentsMargins(0, 0, 0, 0)
        labels.setSpacing(4)
        min_label = QLabel("0.000")
        min_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        label = QLabel("0.000")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        max_label = QLabel("0.000")
        max_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        for text_label in (min_label, label, max_label):
            label_font = text_label.font()
            label_font.setPointSize(max(9, label_font.pointSize()))
            text_label.setFont(label_font)
        slider = _CaretSlider(container)
        slider.setRange(0, DISPLAY_SLIDER_MAX)
        slider.setValue(DISPLAY_SLIDER_CENTER)
        slider.setToolTip("")
        labels.addWidget(min_label)
        labels.addWidget(label, 1)
        labels.addWidget(max_label)
        layout.addLayout(labels)
        layout.addWidget(slider)
        container._min_label = min_label
        container._value_label = label
        container._max_label = max_label
        container._value_slider = slider
        return container

    def _set_load_bar(self, *, row: int, axis_row: AxisRow) -> None:
        container = self.table.cellWidget(row, COL_LOAD)
        if not isinstance(container, _LoadBarWidget):
            container = _LoadBarWidget()
            self.table.setCellWidget(row, COL_LOAD, container)
        container.set_value_pct(axis_row.load_pct)
        container.setToolTip(
            f"load {axis_row.load_pct:.1f}% | 100% marker shown | max {LOAD_BAR_MAX_PCT:.0f}%"
        )

    def _set_diag_cell(self, *, row: int, axis_row: AxisRow) -> None:
        container = self.table.cellWidget(row, COL_DIAG)
        if not isinstance(container, _DiagCellWidget):
            container = self._make_diag_cell_widget()
            self.table.setCellWidget(row, COL_DIAG, container)
        temp_label = container._temp_label
        posdiff_label = container._posdiff_label
        if temp_label is not None:
            temp_label.setText(self._format_temp(axis_row.temp_c))
        if posdiff_label is not None:
            posdiff_label.setText(self._format_posdiff_cm(axis_row.pos_diff_m))
        container.setToolTip(
            f"Temp {axis_row.temp_c:.1f} °C | Δpos {(axis_row.pos_diff_m * 100.0):.2f} cm | raw {axis_row.pos_diff_m:.4f} m"
        )

    @staticmethod
    def _make_diag_cell_widget() -> _DiagCellWidget:
        container = _DiagCellWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)
        temp_label = QLabel("T 0.0°", container)
        posdiff_label = QLabel("Δ 0.00 cm", container)
        for text_label in (temp_label, posdiff_label):
            text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            font = text_label.font()
            font.setPointSize(max(8, font.pointSize() - 1))
            text_label.setFont(font)
        layout.addWidget(temp_label)
        layout.addWidget(posdiff_label)
        container._temp_label = temp_label
        container._posdiff_label = posdiff_label
        return container

    def _set_sync_spinner(self, *, row: int, axis_row: AxisRow) -> None:
        container = self.table.cellWidget(row, COL_SYNC)
        if not isinstance(container, _SyncSpinnerWidget):
            container = self._make_sync_spinner_widget()
            self.table.setCellWidget(row, COL_SYNC, container)
        label = container._label
        if label is None:
            return
        frame, bg, fg = self._sync_visuals(axis_row)
        label.setText(frame)
        label.setStyleSheet(
            "QLabel {"
            f" background-color: {bg};"
            f" color: {fg};"
            " border-radius: 8px;"
            " padding: 1px 0px;"
            " font-weight: 700;"
            "}"
        )
        token = axis_row.system_time_token or "-"
        label.setToolTip(f"SystemTime {token}")
        container.setToolTip(f"SystemTime {token}")

    def _sync_visuals(self, axis_row: AxisRow) -> tuple[str, str, str]:
        unit_id = str(axis_row.unit_id)
        token = str(axis_row.system_time_token or "")
        prev_token, prev_idx = self._sync_progress.get(unit_id, ("", -1))
        if not token:
            self._sync_progress[unit_id] = ("", -1)
            return "·", "#eceff2", "#7a8088"
        if token != prev_token:
            next_idx = (prev_idx + 1) % len(SYNC_FRAMES)
            self._sync_progress[unit_id] = (token, next_idx)
            return SYNC_FRAMES[next_idx], "#dff2df", "#1f6a2e"
        self._sync_progress[unit_id] = (token, prev_idx)
        frame = SYNC_FRAMES[prev_idx] if prev_idx >= 0 else "·"
        phase_name = str(getattr(axis_row.phase, "value", axis_row.phase)).upper()
        if phase_name == "ESTOP":
            return frame, "#f7efbf", "#6d5600"
        return frame, "#eceff2", "#6c737c"

    @staticmethod
    def _make_sync_spinner_widget() -> _SyncSpinnerWidget:
        container = _SyncSpinnerWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(1, 0, 1, 0)
        layout.setSpacing(0)
        label = QLabel("·", container)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = label.font()
        font.setPointSize(max(10, font.pointSize() + 1))
        label.setFont(font)
        layout.addWidget(label, 1)
        container._label = label
        return container

    @staticmethod
    def _format_temp(temp_c: float) -> str:
        return f"T {float(temp_c):.1f}°"

    @staticmethod
    def _format_posdiff_cm(pos_diff_m: float) -> str:
        return f"Δ {float(pos_diff_m) * 100.0:.2f} cm"

    @staticmethod
    def _position_limits(row: AxisRow) -> tuple[float, float]:
        raw_min = getattr(row, "pos_user_min", None)
        raw_max = getattr(row, "pos_user_max", None)
        if raw_min is None or raw_max is None:
            fallback = max(abs(float(row.pos)), 1.0)
            return -fallback, fallback
        return float(raw_min), float(raw_max)

    @staticmethod
    def _slider_value_for_signed_display(value: float, abs_span: float) -> int:
        span = max(float(abs_span), 1.0)
        clipped = max(-span, min(span, float(value)))
        normalized = (clipped + span) / (2.0 * span)
        return int(round(normalized * DISPLAY_SLIDER_MAX))

    @staticmethod
    def _slider_value_for_range(value: float, minimum: float, maximum: float) -> int:
        lo = float(minimum)
        hi = float(maximum)
        if hi < lo:
            lo, hi = hi, lo
        if abs(hi - lo) < 1e-9:
            lo -= 1.0
            hi += 1.0
        clipped = max(lo, min(hi, float(value)))
        normalized = (clipped - lo) / (hi - lo)
        return int(round(normalized * DISPLAY_SLIDER_MAX))

    @staticmethod
    def _display_velocity_span(rows: list[AxisRow]) -> float:
        vel_span = max((abs(float(row.vel)) for row in rows), default=1.0)
        return max(vel_span, 1.0)
