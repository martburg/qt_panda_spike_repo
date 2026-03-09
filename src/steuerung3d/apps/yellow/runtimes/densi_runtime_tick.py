from __future__ import annotations

from typing import TYPE_CHECKING

from steuerung3d.core.command_frame import CommandFrame

if TYPE_CHECKING:
    from .densi_runtime_impl import DensiRuntime


def edge_log_cmd_changes(rt: "DensiRuntime", cmd: CommandFrame | None) -> None:
    try:
        if rt._ch.changed("cmd_core_mode", str(getattr(cmd, "core_mode", ""))):
            rt._log.info("cmd_core_mode=%s", getattr(cmd, "core_mode", ""))
        if rt._ch.changed("cmd_estop_reset", bool(getattr(cmd, "estop_reset", False))):
            rt._log.info("cmd_estop_reset=%s", bool(getattr(cmd, "estop_reset", False)))
    except Exception:
        pass


def handle_gui_not_halt_cmd(rt: "DensiRuntime", cmd: CommandFrame | None) -> None:
    try:
        if rt._ch.changed("cmd_gui_not_halt", bool(getattr(cmd, "gui_not_halt", False))):
            rt._log.info("gui_not_halt=%s", bool(getattr(cmd, "gui_not_halt", False)))
    except Exception:
        pass
