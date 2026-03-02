# src/steuerung3d/protocol/drive_status.py
from __future__ import annotations

from dataclasses import dataclass

# Legacy bit meanings (from your Decoder.py):
# bit0: Output powered
# bit1: AMP ready
# bit2: Referenced
# bit3: In Position
# bit4: Brake lifted
# bit5: Fault bit (1 = fault)
# bit6: Right end switch contacted
# bit7: Left end switch contacted
# bits8..: Zustand (state / error code)  => value >> 8
#
# Special legacy input strings:
#  - "SIMUL": force everything "SIMUL"
#  - "0": treat as NoConn
#
# Source: your legacy decoder snippet. :contentReference[oaicite:0]{index=0}


@dataclass(frozen=True)
class DriveStatus:
    raw: int
    # base bits
    output_powered: bool
    amp_ready: bool
    referenced: bool
    in_position: bool
    brake_lifted: bool
    fault: bool
    right_end_switch: bool
    left_end_switch: bool

    # derived
    zustand: int  # raw >> 8
    label: str  # human-ish text
    is_simul: bool = False
    is_noconn: bool = False

    def summary(self) -> str:
        """Compact text for the legacy 'AmpStatus' line edits."""
        if self.is_simul:
            return "SIMUL"
        if self.is_noconn:
            return "NoConn"
        # Keep this short; you already show age separately in banner.
        # Example: "Ready | Ref | OK"
        parts: list[str] = []
        parts.append("Pwr" if self.output_powered else "NoPwr")
        parts.append("Ready" if self.amp_ready else "NotReady")
        if self.referenced:
            parts.append("Ref")
        if self.in_position:
            parts.append("InPos")
        if self.fault:
            parts.append("FAULT")
        # Zustand label last (helps to read quickly)
        if self.label:
            parts.append(self.label)
        return " ".join(parts)


# --- Legacy Zustand mappings (no-fault branch) ---
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

# --- Legacy error codes (fault branch) ---
# NOTE: your original code sometimes compares to str(Zustand); we normalize to int keys here.
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


def decode_drive_status(word: int | str | None) -> DriveStatus:
    """
    Decode the legacy amplifier status word into a structured object.

    Accepts:
      - int (normal)
      - str (legacy UI sometimes passed strings: "SIMUL", "0", "1234")
      - None (treated as NoConn)
    """
    if word is None:
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

    if isinstance(word, str):
        w = word.strip()
        if w.upper() == "SIMUL":
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
        if w == "0" or w == "":
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
        try:
            word_i = int(w, 0)  # allow "123", "0x10"
        except Exception:
            word_i = 0
        word = word_i

    raw = int(word) & 0xFFFFFFFF

    # bits
    b0 = bool(raw & (1 << 0))
    b1 = bool(raw & (1 << 1))
    b2 = bool(raw & (1 << 2))
    b3 = bool(raw & (1 << 3))
    b4 = bool(raw & (1 << 4))
    b5 = bool(raw & (1 << 5))  # fault
    b6 = bool(raw & (1 << 6))
    b7 = bool(raw & (1 << 7))

    zustand = int(raw >> 8)

    if not b5:
        label = _ZUSTAND_OK_LABELS.get(zustand, "Unknown")
    else:
        label = _ZUSTAND_ERR_LABELS.get(zustand, "-Unknown Error")

    return DriveStatus(
        raw=raw,
        output_powered=b0,
        amp_ready=b1,
        referenced=b2,
        in_position=b3,
        brake_lifted=b4,
        fault=b5,
        right_end_switch=b6,
        left_end_switch=b7,
        zustand=zustand,
        label=label,
        is_simul=False,
        is_noconn=False,
    )


# --------------------------------------------------------------------
# Drop-in note for HiPController:
#   from steuerung3d.protocol.drive_status import decode_drive_status
# --------------------------------------------------------------------
