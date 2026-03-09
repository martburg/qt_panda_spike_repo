from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias, TypedDict


@dataclass(frozen=True)
class DriveStatus:
    raw: int
    output_powered: bool
    amp_ready: bool
    referenced: bool
    in_position: bool
    brake_lifted: bool
    fault: bool
    right_end_switch: bool
    left_end_switch: bool
    zustand: int
    label: str
    is_simul: bool = False
    is_noconn: bool = False

    def summary(self) -> str:
        if self.is_simul:
            return "SIMUL"
        if self.is_noconn:
            return "NoConn"
        parts: list[str] = []
        parts.append("Pwr" if self.output_powered else "NoPwr")
        parts.append("Ready" if self.amp_ready else "NotReady")
        if self.referenced:
            parts.append("Ref")
        if self.in_position:
            parts.append("InPos")
        if self.fault:
            parts.append("FAULT")
        if self.label:
            parts.append(self.label)
        return " ".join(parts)


_ZUSTAND_OK_LABELS: dict[int, str] = {
    0: "Not Ready",
    1: "Locked",
    2: "Not Enabled",
    3: "Heating",
    4: "VCC-Mode",
    5: "Guider",
    6: "M-Regelung",
    7: "Holding",
    8: "Factory Reset",
    9: "Stops contacted",
    10: "Ready",
    11: "Referenzfahrt",
    12: "Fangen",
    13: "Geber einmessen",
    14: "Fehler",
    15: "Handbetrieb",
    16: "TimeOut",
    17: "Save Stop",
}

_ZUSTAND_ERR_LABELS: dict[int, str] = {
    1: "-Ueberstrom",
    3: "-Erdschluss",
    4: "-Bremschopper",
    6: "-Netzphasenausfall",
    7: "-Zwischenkreis Ueberspannung",
    8: "-Drehzahlueberwachung",
    9: "-Inbetriebnahme",
    10: "-IPOS-ILLOP",
    11: "-Uebertemperatur",
    13: "-Steuerquelle",
    14: "-Geber",
    17: "-Stack Overflow",
    18: "-Stack Underflow",
    19: "-External NMI",
    20: "-Undefined OP-Code",
    21: "-Protection Fault",
    22: "-Illegal Word Operand",
    23: "-Illegal Instruction Access",
    24: "-Illegal External Bus Access",
    25: "-EEPROM",
    26: "-Externe Klemme",
    27: "-Endschalter fehlen",
    28: "-Feldbus Timeout",
    29: "-Endschalter angefahren",
    30: "-Notstop Timout",
    31: "-TF/TH Ausloeser",
    32: "-IPOS-Index Overflow",
    33: "-Sollwert Quelle",
    34: "-Rampen Timeout",
    35: "-Betriebsart",
    36: "-Option Missing",
    37: "-System Watchdog",
    38: "-System Software",
    39: "-Referenzfahrt",
    40: "-Boot Synchronisation",
    41: "-Watchdog Option",
    42: "-Schleppfehler",
    43: "-RS485 Timeout",
    44: "-Geraeteauslastung",
    45: "-Initialisierung",
    46: "-Systembus 2 Timeout",
    47: "-Systembus 1 Timeout",
    48: "-Hardware DRS",
    77: "-IPOS.Steuerwort",
    78: "-IPOS.SW Endschalter",
    79: "-Hardware Konfiguration",
    80: "-RAM-Test",
    81: "-Starting Kondition",
    82: "-Ausgang offen",
    84: "-Motorschutz",
    86: "-Speichermodul",
    87: "-Technologie Option",
    88: "-Fangen",
    92: "-DIP Geber Problem",
    93: "-DIP Geber Fehler",
    94: "-Checksum EEPROM",
    95: "-DIP-Plausibilitaetsfehler",
    97: "-Kopierfehler",
    98: "-CRC Error",
    99: "-IPOS.Rampenberechnung",
    100: "-Schwingungs Warnung",
    101: "-Schwingungs Fehler",
    102: "-Oelalterung Warnung",
    103: "-Oelalterung Fehler",
    104: "-Oelalterung Ueberthemperatur",
    105: "-Oelalterung Sensor",
    106: "-Bremsen Verschleiss",
    107: "-Netzkomponenten",
    108: "-Fehler DCS",
    109: "-Alarm DCS",
    110: "-Error EX.Schutz",
    113: "-Drahtbruch Analogeingang",
    116: "-Timout MoviPLC",
    123: "-Positionierunterbrechung",
    124: "-Umgebungsbedingungen",
    196: "-Leistungsteil",
    197: "-Netz",
    199: "-Zwischenkreisaufladung",
}


def _noconn_status() -> DriveStatus:
    return DriveStatus(
        raw=0,
        output_powered=False,
        amp_ready=False,
        referenced=False,
        in_position=False,
        brake_lifted=False,
        fault=False,
        right_end_switch=False,
        left_end_switch=False,
        zustand=0,
        label="NoConn",
        is_simul=False,
        is_noconn=True,
    )


def _simul_status() -> DriveStatus:
    return DriveStatus(
        raw=0,
        output_powered=True,
        amp_ready=True,
        referenced=True,
        in_position=True,
        brake_lifted=True,
        fault=False,
        right_end_switch=True,
        left_end_switch=True,
        zustand=0,
        label="SIMUL",
        is_simul=True,
        is_noconn=False,
    )


DriveStatusWord: TypeAlias = int | str | None


def _coerce_word(word: DriveStatusWord) -> int | None:
    if word is None:
        return None
    if isinstance(word, str):
        w = word.strip()
        if w.upper() == "SIMUL":
            return -1
        if w == "0" or w == "":
            return None
        try:
            return int(w, 0)
        except Exception:
            return 0
    return int(word)


class _DriveStatusFields(TypedDict):
    raw: int
    output_powered: bool
    amp_ready: bool
    referenced: bool
    in_position: bool
    brake_lifted: bool
    fault: bool
    right_end_switch: bool
    left_end_switch: bool
    zustand: int
    label: str


def _decode_bit_fields(raw: int) -> _DriveStatusFields:
    return {
        "raw": raw,
        "output_powered": bool(raw & (1 << 0)),
        "amp_ready": bool(raw & (1 << 1)),
        "referenced": bool(raw & (1 << 2)),
        "in_position": bool(raw & (1 << 3)),
        "brake_lifted": bool(raw & (1 << 4)),
        "fault": bool(raw & (1 << 5)),
        "right_end_switch": bool(raw & (1 << 6)),
        "left_end_switch": bool(raw & (1 << 7)),
        "zustand": int(raw >> 8),
        "label": "",
    }


def _decode_label(*, fault: bool, zustand: int) -> str:
    if not fault:
        return _ZUSTAND_OK_LABELS.get(zustand, "Unknown")
    return _ZUSTAND_ERR_LABELS.get(zustand, "-Unknown Error")


def _build_drive_status(fields: _DriveStatusFields) -> DriveStatus:
    return DriveStatus(
        raw=int(fields["raw"]),
        output_powered=bool(fields["output_powered"]),
        amp_ready=bool(fields["amp_ready"]),
        referenced=bool(fields["referenced"]),
        in_position=bool(fields["in_position"]),
        brake_lifted=bool(fields["brake_lifted"]),
        fault=bool(fields["fault"]),
        right_end_switch=bool(fields["right_end_switch"]),
        left_end_switch=bool(fields["left_end_switch"]),
        zustand=int(fields["zustand"]),
        label=str(fields["label"]),
        is_simul=False,
        is_noconn=False,
    )


def decode_drive_status(word: DriveStatusWord) -> DriveStatus:
    coerced = _coerce_word(word)
    if coerced is None:
        return _noconn_status()
    if coerced == -1:
        return _simul_status()

    raw = int(coerced) & 0xFFFFFFFF
    fields = _decode_bit_fields(raw)
    fields["label"] = _decode_label(
        fault=bool(fields["fault"]),
        zustand=int(fields["zustand"]),
    )
    return _build_drive_status(fields)
