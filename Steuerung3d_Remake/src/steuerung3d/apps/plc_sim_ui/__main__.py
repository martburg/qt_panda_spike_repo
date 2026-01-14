# src/steuerung3d/apps/plcsim_ui/main.py
from __future__ import annotations
import sys
from dataclasses import dataclass
from PySide6 import QtCore, QtWidgets



from dataclasses import dataclass
from typing import Dict

@dataclass
class AxisView:
    axis_id: str
    cmd_enable: bool
    cmd_pos: float
    cmd_vel: float
    meas_pos: float
    meas_vel: float
    ready: bool
    powered: bool
    estop_ok: bool
    fault: bool

class PlcSimFacade:
    """Thin wrapper around your actual PLC sim object."""
    def __init__(self, sim):
        self.sim = sim

    def axis_views(self) -> list[AxisView]:
        out = []
        for axis_id, ax in self.sim.axes.items():
            out.append(AxisView(
                axis_id=axis_id,
                cmd_enable=ax.last_cmd.enable,
                cmd_pos=ax.last_cmd.pos,
                cmd_vel=ax.last_cmd.vel,
                meas_pos=ax.meas.pos,
                meas_vel=ax.meas.vel,
                ready=ax.status.ready,
                powered=ax.status.powered,
                estop_ok=ax.status.estop_ok,
                fault=ax.status.fault,
            ))
        return out

    def set_override(self, axis_id: str, *, estop_ok=None, fault=None, comm_drop=None):
        ov = self.sim.overrides[axis_id]
        if estop_ok is not None:
            ov.force_estop_ok = estop_ok
        if fault is not None:
            ov.force_fault = fault
        if comm_drop is not None:
            ov.comm_drop = comm_drop

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, plc: PlcSimFacade):
        super().__init__()
        self.plc = plc
        self.setWindowTitle("PLC Sim UI (MVP)")

        self.table = QtWidgets.QTableWidget(0, 11)
        self.table.setHorizontalHeaderLabels([
            "Axis", "CmdEn", "CmdPos", "CmdVel", "MeasPos", "MeasVel",
            "Ready", "Powered", "EStopOK", "Fault", "CommDrop"
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.setCentralWidget(self.table)

        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(100)  # 10 Hz UI refresh (independent from sim tick)
        self.timer.timeout.connect(self.refresh)
        self.timer.start()

    def refresh(self):
        views = self.plc.axis_views()
        self.table.setRowCount(len(views))

        for r, v in enumerate(views):
            self._set_item(r, 0, v.axis_id)
            self._set_bool(r, 1, v.cmd_enable, readonly=True)
            self._set_item(r, 2, f"{v.cmd_pos:.3f}")
            self._set_item(r, 3, f"{v.cmd_vel:.3f}")
            self._set_item(r, 4, f"{v.meas_pos:.3f}")
            self._set_item(r, 5, f"{v.meas_vel:.3f}")

            self._set_bool(r, 6, v.ready, readonly=True)
            self._set_bool(r, 7, v.powered, readonly=True)

            # These three are "injectable" toggles:
            self._set_toggle(r, 8, v.estop_ok, lambda checked, axis=v.axis_id: self.plc.set_override(axis, estop_ok=checked))
            self._set_toggle(r, 9, v.fault,    lambda checked, axis=v.axis_id: self.plc.set_override(axis, fault=checked))
            self._set_toggle(r,10, False,      lambda checked, axis=v.axis_id: self.plc.set_override(axis, comm_drop=checked))

    def _set_item(self, r, c, text):
        it = QtWidgets.QTableWidgetItem(text)
        it.setFlags(it.flags() & ~QtCore.Qt.ItemIsEditable)
        self.table.setItem(r, c, it)

    def _set_bool(self, r, c, val: bool, readonly: bool):
        cb = QtWidgets.QCheckBox()
        cb.setChecked(bool(val))
        cb.setEnabled(not readonly)
        cb.setStyleSheet("margin-left:12px;")  # small alignment hack
        self.table.setCellWidget(r, c, cb)

    def _set_toggle(self, r, c, val: bool, on_change):
        cb = QtWidgets.QCheckBox()
        cb.setChecked(bool(val))
        cb.stateChanged.connect(lambda state: on_change(state == QtCore.Qt.Checked))
        cb.setStyleSheet("margin-left:12px;")
        self.table.setCellWidget(r, c, cb)

def run(sim):
    app = QtWidgets.QApplication(sys.argv)
    w = MainWindow(PlcSimFacade(sim))
    w.resize(1100, 400)
    w.show()
    sys.exit(app.exec())

# --- Overrides (what the UI toggles) -----------------------------------------

@dataclass
class AxisOverrides:
    force_estop_ok: bool | None = None
    force_fault: bool | None = None
    comm_drop: bool = False


# --- What the UI reads -------------------------------------------------------

@dataclass
class LastCmd:
    enable: bool = False
    pos: float = 0.0
    vel: float = 0.0


@dataclass
class Meas:
    pos: float = 0.0
    vel: float = 0.0


@dataclass
class Status:
    ready: bool = True
    powered: bool = True
    estop_ok: bool = True
    fault: bool = False


class AxisSim:
    def __init__(self, axis_id: str):
        self.axis_id = axis_id
        self.last_cmd = LastCmd()
        self.meas = Meas()
        self.status = Status()


class PlcSimStub:
    """
    Minimal object that satisfies PlcSimFacade expectations:

      sim.axes: dict[str, axis]
      sim.overrides: dict[str, AxisOverrides]
    """

    def __init__(self, axis_ids=("X", "Y", "Z")):
        self.axes: Dict[str, AxisSim] = {aid: AxisSim(aid) for aid in axis_ids}
        self.overrides: Dict[str, AxisOverrides] = {aid: AxisOverrides() for aid in axis_ids}

        # tiny internal time base
        self._t = 0.0

    def tick(self, dt: float = 0.02) -> None:
        """
        Fake some command activity + measurements so UI has something to show.
        In the real sim, your transport/runner would drive this.
        """
        self._t += dt

        for aid, ax in self.axes.items():
            ov = self.overrides[aid]

            # pretend main app commands "enable" after a short time
            ax.last_cmd.enable = self._t > 0.5
            ax.last_cmd.vel = 0.4 if ax.last_cmd.enable else 0.0
            ax.last_cmd.pos += ax.last_cmd.vel * dt

            # measurements follow commanded pos/vel (simple first-order-ish)
            ax.meas.vel = ax.last_cmd.vel
            ax.meas.pos += ax.meas.vel * dt

            # baseline status
            ax.status.ready = True
            ax.status.powered = ax.last_cmd.enable
            ax.status.estop_ok = True
            ax.status.fault = False

            # apply overrides from UI
            if ov.force_estop_ok is not None:
                ax.status.estop_ok = ov.force_estop_ok
            if ov.force_fault is not None:
                ax.status.fault = ov.force_fault

            # derive "ready" from estop/fault (just for demo)
            ax.status.ready = ax.status.estop_ok and (not ax.status.fault)


# --- In your __main__ startup ------------------------------------------------
# In addition to your UI timer refresh, we also tick the stub periodically.

if __name__ == "__main__":
    sim = PlcSimStub(axis_ids=("X", "Y", "Z", "A"))

    # If you used the earlier Qt MainWindow, add a small QTimer that calls sim.tick().
    from PySide6 import QtCore, QtWidgets
    import sys

    app = QtWidgets.QApplication(sys.argv)

    # import or define your run/window here
    # If you have run(sim) already, prefer that.
    # Example: w = MainWindow(PlcSimFacade(sim))

    w = MainWindow(PlcSimFacade(sim))  # uses your earlier classes
    w.resize(1100, 400)
    w.show()

    tick_timer = QtCore.QTimer()
    tick_timer.setInterval(20)  # 50 Hz fake sim tick
    tick_timer.timeout.connect(lambda: sim.tick(0.02))
    tick_timer.start()

    sys.exit(app.exec())
