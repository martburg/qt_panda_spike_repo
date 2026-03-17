from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SupervisorEstopColumn:
    header: str
    key: str
    tooltip: str
    display_true_when_false: bool = False

    def present(self, logical_value: bool) -> bool:
        value = bool(logical_value)
        return (not value) if self.display_true_when_false else value


SUPERVISOR_ESTOP_COLUMNS: tuple[SupervisorEstopColumn, ...] = (
    SupervisorEstopColumn("Master", "master", "Master E-Stop", display_true_when_false=True),
    SupervisorEstopColumn("EStop1", "estop1", "E-Stop 1", display_true_when_false=True),
    SupervisorEstopColumn("30kW", "kw30_ok", "30 kW OK"),
    SupervisorEstopColumn("BRK1OK", "brk1_ok", "Brake 1 OK"),
    SupervisorEstopColumn("SPS", "sps_ok", "SPS OK"),
    SupervisorEstopColumn("PosWin", "pos_win", "Position window"),
    SupervisorEstopColumn("G1Com", "g1_com", "Guider 1 Com"),
    SupervisorEstopColumn("G2Com", "g2_com", "Guider 2 Com"),
    SupervisorEstopColumn("G3Com", "g3_com", "Guider 3 Com"),
    SupervisorEstopColumn("Guider", "guider", "Guider E-Stop", display_true_when_false=True),
    SupervisorEstopColumn("EStop2", "estop2", "E-Stop 2", display_true_when_false=True),
    SupervisorEstopColumn("05kW", "kw05_ok", "0.5 kW OK"),
    SupervisorEstopColumn("BRK2OK", "brk2_ok", "Brake 2 OK"),
    SupervisorEstopColumn("RED", "fbt_ok", "Red / FBT OK"),
    SupervisorEstopColumn("VelWin", "vel_win", "Velocity window"),
    SupervisorEstopColumn("G1Out", "g1_out", "Guider 1 Out"),
    SupervisorEstopColumn("G2Out", "g2_out", "Guider 2 Out"),
    SupervisorEstopColumn("G3Out", "g3_out", "Guider 3 Out"),
    SupervisorEstopColumn("Network", "network", "Network E-Stop", display_true_when_false=True),
    SupervisorEstopColumn("", "", ""),
    SupervisorEstopColumn("", "", ""),
    SupervisorEstopColumn("BRK2KB", "brk2kb_ok", "Brake 2 KB OK"),
    SupervisorEstopColumn("ENC", "dcs_ok", "Encoder / DCS OK"),
    SupervisorEstopColumn("Endlage", "endlage", "Endlage"),
    SupervisorEstopColumn("G1Fb", "g1_fb", "Guider 1 Feedback"),
    SupervisorEstopColumn("G2Fb", "g2_fb", "Guider 2 Feedback"),
    SupervisorEstopColumn("G3Fb", "g3_fb", "Guider 3 Feedback"),
)

ESTOP_GRID_COLUMNS = 9
ESTOP_GRID_ROWS = 3
