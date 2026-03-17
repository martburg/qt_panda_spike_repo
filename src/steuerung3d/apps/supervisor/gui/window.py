from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..models import AxisRow, SupervisorSnapshot
from ..row_estop_dots import ESTOP_GRID_COLUMNS, ESTOP_GRID_ROWS, SUPERVISOR_ESTOP_COLUMNS


DISPLAY_SLIDER_MAX = 1000
DISPLAY_SLIDER_CENTER = DISPLAY_SLIDER_MAX // 2
DOT_SIZE_PX = 8
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
    "selected",
    "diff",
    "EStop",
    "phase(state)",
    "pos",
    "vel",
    "hip",
]

COL_AXIS = 0
COL_SELECTED = 1
COL_DIFF = 2
COL_ESTOP = 3
COL_PHASE = 4
COL_POS = 5
COL_VEL = 6
COL_HIP = 7


class _TooltipDot(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

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
        lay = QVBoxLayout(root)
        self.status_label = QLabel("System: NO PAIRS")
        lay.addWidget(self.status_label)
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
        lay.addLayout(toolbar)
        self.table = QTableWidget(0, len(HEADERS))
        self.table.setHorizontalHeaderLabels(HEADERS)
        self._configure_column_widths()
        lay.addWidget(self.table)
        self.setCentralWidget(root)
        self.setStyleSheet("QToolTip { font-size: 12pt; padding: 8px 10px; }")
        self.btn_reset.clicked.connect(self.reset_estop_clicked.emit)
        self.btn_estart.clicked.connect(self.estart_clicked.emit)
        self.btn_resync.clicked.connect(self.resync_clicked.emit)
        self.btn_recover.clicked.connect(self.recover_clicked.emit)
        self.chk_taster.toggled.connect(self.chk_es_taster_changed.emit)
        self._updating = False

    def apply_snapshot(self, snap: SupervisorSnapshot) -> None:
        self._updating = True
        try:
            self.setWindowTitle(str(snap.title))
            self.status_label.setText(str(snap.status_text))
            rows = list(snap.rows)
            locked = int(getattr(snap, "hip_open_total", 0) or 0) > 0
            pos_span, vel_span = self._display_spans(rows)
            self.btn_reset.setEnabled(not locked)
            self.btn_estart.setEnabled(not locked)
            self.btn_resync.setEnabled(not locked)
            self.chk_taster.setEnabled(not locked)
            if locked:
                self.chk_taster.blockSignals(True)
                self.chk_taster.setChecked(False)
                self.chk_taster.blockSignals(False)
            self.table.setRowCount(len(rows))
            for row_idx, row in enumerate(rows):
                self.table.setRowHeight(row_idx, 58)
                self._set_text(row_idx, COL_AXIS, row.axis_id)
                chk = self.table.cellWidget(row_idx, COL_SELECTED)
                if not isinstance(chk, QCheckBox):
                    chk = QCheckBox()
                    chk.toggled.connect(
                        lambda checked, unit_id=row.unit_id: self._emit_unit_selected(
                            unit_id, checked
                        )
                    )
                    self.table.setCellWidget(row_idx, COL_SELECTED, chk)
                chk.blockSignals(True)
                chk.setChecked(bool(row.selected))
                chk.setEnabled(not locked)
                chk.blockSignals(False)
                self._set_text(row_idx, COL_DIFF, str(int(row.livetick_diff)))
                self._set_estop_block(row_idx=row_idx, row=row)
                self._set_text(row_idx, COL_PHASE, row.phase.value)
                self._set_value_slider(
                    row=row_idx,
                    col=COL_POS,
                    value=float(row.pos),
                    slider_value=self._slider_value_for_signed_display(row.pos, pos_span),
                )
                self._set_value_slider(
                    row=row_idx,
                    col=COL_VEL,
                    value=float(row.vel),
                    slider_value=self._slider_value_for_signed_display(row.vel, vel_span),
                )
                btn = self.table.cellWidget(row_idx, COL_HIP)
                if not isinstance(btn, QPushButton):
                    btn = QPushButton()
                    btn.clicked.connect(
                        lambda _checked=False, unit_id=row.unit_id: self.open_hip_clicked.emit(
                            unit_id
                        )
                    )
                    self.table.setCellWidget(row_idx, COL_HIP, btn)
                btn.setText(self._hip_button_text(int(row.hip_open_count)))
            while self.table.rowCount() > len(rows):
                self.table.removeRow(self.table.rowCount() - 1)
        finally:
            self._updating = False

    def show_recover_placeholder(self) -> None:
        QMessageBox.information(self, "Recover", "Recover not implemented yet.")

    def _emit_unit_selected(self, unit_id: str, checked: bool) -> None:
        if self._updating:
            return
        normalized_unit_id = str(unit_id)
        normalized_checked = bool(checked)
        self.unit_selected_changed.emit(normalized_unit_id, normalized_checked)
        self.pair_selected_changed.emit(normalized_unit_id, normalized_checked)

    def _emit_pair_selected(self, pair_id: str, checked: bool) -> None:
        self._emit_unit_selected(pair_id, checked)

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
                item.setTextAlignment(int(Qt.AlignCenter))
            self.table.setItem(row, col, item)
        item.setText(text)

    def _configure_column_widths(self) -> None:
        self.table.setColumnWidth(COL_AXIS, 110)
        self.table.setColumnWidth(COL_SELECTED, 70)
        self.table.setColumnWidth(COL_DIFF, 55)
        self.table.setColumnWidth(COL_ESTOP, 190)
        self.table.setColumnWidth(COL_PHASE, 96)
        self.table.setColumnWidth(COL_POS, 160)
        self.table.setColumnWidth(COL_VEL, 160)
        self.table.setColumnWidth(COL_HIP, 110)
        self.table.verticalHeader().setDefaultSectionSize(58)

    def _set_estop_block(self, *, row_idx: int, row: AxisRow) -> None:
        container = self.table.cellWidget(row_idx, COL_ESTOP)
        if not isinstance(container, QWidget):
            container = self._make_estop_block_widget()
            self.table.setCellWidget(row_idx, COL_ESTOP, container)
        cells = getattr(container, "_cells", None)
        if not isinstance(cells, list):
            return
        states = tuple(row.estop_dots)
        for idx, column in enumerate(SUPERVISOR_ESTOP_COLUMNS):
            if idx >= len(cells):
                break
            dot = cells[idx]
            if not isinstance(dot, _TooltipDot):
                continue
            state = states[idx] if idx < len(states) else None
            label = column.header
            self._set_dot_state(dot, state=state, label=label)
            parent = dot.parentWidget()
            grandparent = parent.parentWidget() if parent is not None else None
            tooltip = label if label else ""
            if parent is not None:
                parent.setToolTip(tooltip)
            if grandparent is not None:
                grandparent.setToolTip(tooltip)

    @staticmethod
    def _make_estop_block_widget() -> QWidget:
        container = QWidget()
        grid = QGridLayout(container)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(1)
        grid.setVerticalSpacing(1)
        cells: list[QFrame] = []
        for row in range(ESTOP_GRID_ROWS):
            for col in range(ESTOP_GRID_COLUMNS):
                idx = row * ESTOP_GRID_COLUMNS + col
                column = SUPERVISOR_ESTOP_COLUMNS[idx]
                cell = QWidget(container)
                cell_layout = QVBoxLayout(cell)
                cell_layout.setContentsMargins(0, 0, 0, 0)
                cell_layout.setSpacing(0)
                cell.setContentsMargins(0, 0, 0, 0)
                dot_wrap = QWidget(cell)
                dot_wrap_layout = QHBoxLayout(dot_wrap)
                dot_wrap_layout.setContentsMargins(0, 0, 0, 0)
                dot_wrap_layout.setSpacing(0)
                dot_wrap_layout.setAlignment(Qt.AlignCenter)
                dot = _TooltipDot(dot_wrap)
                dot.setStyleSheet(DOT_YELLOW_STYLE)
                dot_wrap.setToolTip(column.header)
                cell.setToolTip(column.header)
                if not column.header:
                    dot.setVisible(False)
                    dot_wrap.setToolTip("")
                    cell.setToolTip("")
                dot_wrap_layout.addWidget(dot)
                cell_layout.addWidget(dot_wrap)
                grid.addWidget(cell, row, col)
                cells.append(dot)
        setattr(container, "_cells", cells)
        return container

    @staticmethod
    def _set_dot_state(dot: _TooltipDot, *, state: bool | None, label: str) -> None:
        if state is None:
            dot.setStyleSheet(DOT_YELLOW_STYLE)
        elif bool(state):
            dot.setStyleSheet(DOT_GREEN_STYLE)
        else:
            dot.setStyleSheet(DOT_RED_STYLE)

    def _set_value_slider(self, *, row: int, col: int, value: float, slider_value: int) -> None:
        container = self.table.cellWidget(row, col)
        if not isinstance(container, QWidget):
            container = self._make_value_slider_widget()
            self.table.setCellWidget(row, col, container)
        label = getattr(container, "_value_label", None)
        slider = getattr(container, "_value_slider", None)
        if isinstance(label, QLabel):
            label.setText(f"{float(value):.3f}")
        if isinstance(slider, QSlider):
            slider.setValue(int(slider_value))
            slider.setToolTip(f"{float(value):.3f}")

    @staticmethod
    def _make_value_slider_widget() -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(1, 0, 1, 0)
        layout.setSpacing(0)
        label = QLabel("0.000")
        label.setAlignment(Qt.AlignCenter)
        label_font = label.font()
        label_font.setPointSize(max(7, label_font.pointSize() - 2))
        label.setFont(label_font)
        slider = QSlider(Qt.Horizontal)
        slider.setRange(0, DISPLAY_SLIDER_MAX)
        slider.setValue(DISPLAY_SLIDER_CENTER)
        slider.setEnabled(False)
        layout.addWidget(label)
        layout.addWidget(slider)
        setattr(container, "_value_label", label)
        setattr(container, "_value_slider", slider)
        return container

    @staticmethod
    def _slider_value_for_signed_display(value: float, abs_span: float) -> int:
        span = max(float(abs_span), 1.0)
        clipped = max(-span, min(span, float(value)))
        normalized = (clipped + span) / (2.0 * span)
        return int(round(normalized * DISPLAY_SLIDER_MAX))

    @staticmethod
    def _display_spans(rows: list[AxisRow]) -> tuple[float, float]:
        pos_span = max((abs(float(row.pos)) for row in rows), default=1.0)
        vel_span = max((abs(float(row.vel)) for row in rows), default=1.0)
        return max(pos_span, 1.0), max(vel_span, 1.0)
