from __future__ import annotations

def decode_estop_active(estop_status_dword: int) -> bool:
    # TODO: map real bits once known; for now treat any nonzero as "E-stop / safety not ok"
    return estop_status_dword != 0

def decode_fault_active(status_word: int) -> bool:
    # TODO: map real bits; conservative placeholder
    # if you already know a "fault" bit, put it here.
    return False

def decode_enabled(status_word: int) -> bool:
    # TODO: map real bits; conservative placeholder
    return False
