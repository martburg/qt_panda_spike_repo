from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DriveStatusDecoded:
    raw: int
    state_id: int
    state_label: str
    is_simul: bool
    is_no_conn: bool

    # bit flags (from legacy Decoder.py)
    output_powered: bool
    amp_ready: bool
    referenced: bool
    in_position: bool
    brake_lifted: bool
    end_right: bool
    end_left: bool

    is_fault: bool

    def summary(self) -> str:
        base = self.state_label
        if self.is_no_conn:
            base = "No Conn"
        elif self.is_simul:
            base = "SIMUL"
        if self.is_fault:
            # state_id is negative in legacy mapping, but keep label too
            return f"FAULT: {base}"
        return base


# Legacy mapping from 'Zustand' to string. Ported from Decoder.py (3DSteuerung legacy).
_STATE_MAP = {
    0: "Not Connected",
    1: "General Reset",
    2: "MC Reset",
    3: "Drive OFF",
    4: "Wait for Power",
    5: "Wait for IGBTs",
    6: "Ready to run",
    7: "Waiting for Enable",
    8: "Starting",
    9: "Enable",
    10: "Ready",
    11: "Deccelerate to stop",
    12: "Fast stop",
    13: "Disable",
    14: "Wait for Idle",
    15: "Initialising - Referencing",
    16: "Referencing",
    17: "Wait for Reference",
    18: "Positioning",
    19: "Stop",
    20: "Homing",
    21: "Stop",
    22: "Quick Stop",
    23: "Jogging",
    24: "Correction",
    25: "Wait for Brake1",
    26: "Wait for Brake2",
    27: "Shutting Down",
}

_FAULT_MAP = {
    1: "Overcurrent",
    2: "Overvoltage",
    3: "Undervoltage",
    4: "Overtemperature",
    5: "Motor temp. sensor",
    6: "Feedback error",
    7: "Motor blocked",
    8: "Max speed reached",
    9: "Motor phase error",
    10: "Power stage error",
    11: "CAN / bus error",
    12: "Internal error",
    13: "Load exceeded",
    14: "Safety circuit open",
}


def decode_drive_status(word: int) -> DriveStatusDecoded:
    """Decode legacy drive status word (Status / GuideStatus).

    The legacy UI treated this as a bitfield with an embedded 0..31 'Zustand' value.
    This is not a normative spec; it is ported behavior for UI compatibility.
    """
    try:
        raw = int(word) & 0xFFFF
    except Exception:
        raw = 0

    # Special legacy values
    if raw == 65535:
        return DriveStatusDecoded(
            raw=raw,
            state_id=0,
            state_label="SIMUL",
            is_simul=True,
            is_no_conn=False,
            output_powered=False,
            amp_ready=False,
            referenced=False,
            in_position=False,
            brake_lifted=False,
            end_right=False,
            end_left=False,
            is_fault=False,
        )
    if raw == 0:
        return DriveStatusDecoded(
            raw=raw,
            state_id=0,
            state_label="Not Connected",
            is_simul=False,
            is_no_conn=True,
            output_powered=False,
            amp_ready=False,
            referenced=False,
            in_position=False,
            brake_lifted=False,
            end_right=False,
            end_left=False,
            is_fault=False,
        )

    # Zustand is bits 0..4 (legacy)
    state_id = raw & 0x001F
    state_label = _STATE_MAP.get(state_id, f"State {state_id}")

    # flags (legacy)
    output_powered = bool(raw & 0x0020)
    amp_ready = bool(raw & 0x0040)
    referenced = bool(raw & 0x0080)
    in_position = bool(raw & 0x0100)
    brake_lifted = bool(raw & 0x0200)
    end_right = bool(raw & 0x0400)
    end_left = bool(raw & 0x0800)

    fault_code = (raw & 0xF000) >> 12
    is_fault = fault_code != 0
    if is_fault:
        fault_label = _FAULT_MAP.get(fault_code, f"Fault {fault_code}")
        state_label = f"{state_label} / {fault_label}"

    return DriveStatusDecoded(
        raw=raw,
        state_id=state_id,
        state_label=state_label,
        is_simul=False,
        is_no_conn=False,
        output_powered=output_powered,
        amp_ready=amp_ready,
        referenced=referenced,
        in_position=in_position,
        brake_lifted=brake_lifted,
        end_right=end_right,
        end_left=end_left,
        is_fault=is_fault,
    )
