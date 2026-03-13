from __future__ import annotations

from dataclasses import dataclass

from ...engines.supervisor.models import PairAction, PairInteractionMode, PairPhase, PairStatus


@dataclass(frozen=True)
class SupervisorRowActionFlags:
    can_reset_estop: bool
    can_estart: bool
    can_check_es_taster: bool
    can_edit_parameters: bool
    can_write_parameters: bool
    can_cancel_edit: bool
    can_remove_member: bool


@dataclass(frozen=True)
class AddPairToSupervisor:
    supervisor_id: str
    pair_id: str


@dataclass(frozen=True)
class RemovePairFromSupervisor:
    supervisor_id: str
    pair_id: str


def _titleize(value: str) -> str:
    parts = [part for part in str(value).split("_") if part]
    if not parts:
        return ""
    titled = [part if part == "EsTaster" else part.capitalize() for part in parts]
    return " ".join(titled)


def format_pair_phase(phase: PairPhase) -> str:
    return _titleize(str(phase.value))


def format_interaction_mode(mode: PairInteractionMode) -> str:
    return _titleize(str(mode.value))


def format_position(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{float(value):.2f} m"


def format_velocity(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{float(value):.2f} m/s"


def format_primary_action(action: PairAction | None) -> str:
    if action is None:
        return ""
    if action == PairAction.RESET_ESTOP:
        return "Reset EStop"
    if action == PairAction.CHECK_ES_TASTER:
        return "Check EsTaster"
    if action == PairAction.EDIT_PARAMETERS:
        return "Edit parameters"
    if action == PairAction.WRITE_PARAMETERS:
        return "Write parameters"
    if action == PairAction.CANCEL_EDIT:
        return "Cancel edit"
    if action == PairAction.ESTART:
        return "EStart"
    return _titleize(str(action.value))


def format_reset_estop_reason(reason: str) -> str:
    return str(reason)


def derive_row_action_flags(status: PairStatus) -> SupervisorRowActionFlags:
    allowed = status.actions.allowed_actions
    return SupervisorRowActionFlags(
        can_reset_estop=PairAction.RESET_ESTOP in allowed,
        can_estart=PairAction.ESTART in allowed,
        can_check_es_taster=PairAction.CHECK_ES_TASTER in allowed,
        can_edit_parameters=PairAction.EDIT_PARAMETERS in allowed,
        can_write_parameters=PairAction.WRITE_PARAMETERS in allowed,
        can_cancel_edit=PairAction.CANCEL_EDIT in allowed,
        can_remove_member=True,
    )


def resolve_selected_pair_status(
    statuses: dict[str, PairStatus],
    selected_pair_id: str | None,
) -> PairStatus | None:
    if not selected_pair_id:
        return None
    return statuses.get(str(selected_pair_id))
