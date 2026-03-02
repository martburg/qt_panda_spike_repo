"""Drive status word helpers for DenSi engine (Qt-free)."""

from __future__ import annotations

from steuerung3d.core.state import MachineState

from ...domain.estop_facts import decode_estop_word


def make_drive_status_word(
    *,
    output_powered: bool,
    amp_ready: bool,
    referenced: bool,
    in_position: bool,
    brake_lifted: bool,
    fault: bool,
    zustand: int,
) -> int:
    w = 0
    if output_powered:
        w |= 1 << 0
    if amp_ready:
        w |= 1 << 1
    if referenced:
        w |= 1 << 2
    if in_position:
        w |= 1 << 3
    if brake_lifted:
        w |= 1 << 4
    if fault:
        w |= 1 << 5
    w |= (int(zustand) & 0xFF) << 8
    return int(w)


def update_drive_status_words(*, state: MachineState, inj_estop_word: int, drive_ready: bool) -> None:
    bits = decode_estop_word(int(inj_estop_word))
    taster = bool(bits.get("taster", False))

    for _axis_id, ax in state.axes.items():
        vel = float(getattr(ax, "vel", 0.0) or 0.0)
        in_pos = abs(vel) < 1e-3

        if bool(state.estop):
            main = make_drive_status_word(
                output_powered=False,
                amp_ready=False,
                referenced=False,
                in_position=False,
                brake_lifted=False,
                fault=True,
                zustand=14,
            )
            slave = make_drive_status_word(
                output_powered=False,
                amp_ready=False,
                referenced=False,
                in_position=False,
                brake_lifted=False,
                fault=True,
                zustand=14,
            )
        elif bool(drive_ready) and taster:
            main = make_drive_status_word(
                output_powered=True,
                amp_ready=True,
                referenced=True,
                in_position=in_pos,
                brake_lifted=True,
                fault=False,
                zustand=10,
            )
            slave = make_drive_status_word(
                output_powered=True,
                amp_ready=True,
                referenced=True,
                in_position=in_pos,
                brake_lifted=True,
                fault=False,
                zustand=5,
            )
        else:
            main = make_drive_status_word(
                output_powered=False,
                amp_ready=False,
                referenced=False,
                in_position=False,
                brake_lifted=False,
                fault=False,
                zustand=0,
            )
            slave = make_drive_status_word(
                output_powered=False,
                amp_ready=False,
                referenced=False,
                in_position=False,
                brake_lifted=False,
                fault=False,
                zustand=0,
            )

        ax.meta["status_word"] = int(main)
        ax.meta["guide_status_word"] = int(slave)
