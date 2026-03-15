from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
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

from ..models import SupervisorSnapshot


class SupervisorWindow(QMainWindow):
    reset_estop_clicked = Signal()
    estart_clicked = Signal()
    resync_clicked = Signal()
    recover_clicked = Signal()
    chk_es_taster_changed = Signal(bool)
    pair_selected_changed = Signal(str, bool)
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
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            ["axis", "selected", "phase(state)", "estop", "livetick", "pos", "vel", "hip"]
        )
        lay.addWidget(self.table)
        self.setCentralWidget(root)
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
            self.table.setRowCount(len(rows))
            for row_idx, row in enumerate(rows):
                self._set_text(row_idx, 0, row.axis_id)
                chk = self.table.cellWidget(row_idx, 1)
                if not isinstance(chk, QCheckBox):
                    chk = QCheckBox()
                    chk.toggled.connect(
                        lambda checked, unit_id=row.unit_id: self._emit_pair_selected(unit_id, checked)
                    )
                    self.table.setCellWidget(row_idx, 1, chk)
                chk.blockSignals(True)
                chk.setChecked(bool(row.selected))
                chk.blockSignals(False)
                self._set_text(row_idx, 2, row.phase.value)
                self._set_text(row_idx, 3, "yes" if row.estop else "no")
                self._set_text(row_idx, 4, str(int(row.livetick)))
                self._set_text(row_idx, 5, f"{row.pos:.3f}")
                self._set_text(row_idx, 6, f"{row.vel:.3f}")
                btn = self.table.cellWidget(row_idx, 7)
                if not isinstance(btn, QPushButton):
                    btn = QPushButton()
                    btn.clicked.connect(lambda _checked=False, unit_id=row.unit_id: self.open_hip_clicked.emit(unit_id))
                    self.table.setCellWidget(row_idx, 7, btn)
                btn.setText(self._hip_button_text(int(row.hip_open_count)))
            while self.table.rowCount() > len(rows):
                self.table.removeRow(self.table.rowCount() - 1)
        finally:
            self._updating = False

    def show_recover_placeholder(self) -> None:
        QMessageBox.information(self, "Recover", "Recover not implemented yet.")

    def _emit_pair_selected(self, pair_id: str, checked: bool) -> None:
        if self._updating:
            return
        self.pair_selected_changed.emit(str(pair_id), bool(checked))

    @staticmethod
    def _hip_button_text(open_count: int) -> str:
        if int(open_count) <= 0:
            return "Open HiP"
        return f"Open HiP ({int(open_count)})"

    def _set_text(self, row: int, col: int, text: str) -> None:
        item = self.table.item(row, col)
        if item is None:
            item = QTableWidgetItem()
            if col != 0:
                item.setTextAlignment(int(Qt.AlignCenter))
            self.table.setItem(row, col, item)
        item.setText(text)
