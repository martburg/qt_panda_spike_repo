"""Qt-free HiP engine (minimal seam).

Purpose: provide a stable place to compute attach-state enablement and banner
estate without changing controller behavior. This is used for shadow-mode
comparison before cutover.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any, Iterable

from steuerung3d.core.intents import EchoLifeTick, Intent
from steuerung3d.core.telemetry import TelemetrySnapshot

from ...domain.param_txn import ParamEditTxnClient
from ...domain.taster_edge_state import (
    TasterEdgeState,
    update_taster_edge_state,
    within_brake_grace,
)
from .attach_state import compute_attach_state
from .intent_policy import gate_motion_intents, is_motion_intent
from .presentation import compute_banner_estate
from .step_impl import step as _step
from .types import (
    HipAttachInputs,
    HipBannerInputs,
    HipParamAction,
    HipParamButtons,
    HipParamGroup,
    HipParamUiState,
    HipState,
    HipStepInputs,
    HipStepResult,
    HipUiInputs,
)
from .viewmodel import HipViewModel

log = logging.getLogger("hi_p")

# Public surface: keep these names importable from this module for call sites
# that treat engine.py as the stable seam. (Used by Qt binder & shadow-mode wiring.)
__all__ = [
    "HipEngine",
    "HipViewModel",
    "HipAttachInputs",
    "HipBannerInputs",
    "HipParamAction",
    "HipUiInputs",
    "HipState",
    "HipStepInputs",
    "HipStepResult",
]


class HipEngine:
    """Minimal HipEngine surface (shadow-mode only)."""

    def __init__(self, *, hip_id: str = "") -> None:
        self._param_txn = ParamEditTxnClient(hip_id=str(hip_id or ""))
        self._taster_state: dict[str, TasterEdgeState] = {}
        self.state = HipState()

    @staticmethod
    def _is_motion_intent(intent: object) -> bool:
        return is_motion_intent(intent)

    def _gate_motion_intents(self, intents: Iterable[object], *, deadman: bool) -> list[object]:
        return gate_motion_intents(intents, deadman=deadman)

    def _update_taster_edge(self, axis_id: str, taster: bool, now_s: float) -> None:
        prev = self._taster_state.get(axis_id, TasterEdgeState())
        self._taster_state[axis_id] = update_taster_edge_state(
            state=prev,
            taster=bool(taster),
            now_s=float(now_s),
        )

    def _within_brake_grace(self, axis_id: str, now_s: float, grace_s: float) -> bool:
        state = self._taster_state.get(axis_id, TasterEdgeState())
        return within_brake_grace(state=state, now_s=float(now_s), grace_s=float(grace_s))

    def compute_attach_state(self, inputs: HipAttachInputs):
        return compute_attach_state(inputs)

    def compute_banner_estate(self, inputs: HipBannerInputs) -> str:
        return compute_banner_estate(
            estop_word=int(inputs.estop_word),
            within_brake_grace=bool(inputs.within_brake_grace),
        )

    def step(self, inputs: HipStepInputs) -> HipStepResult:
        return _step(engine=self, inputs=inputs)

    @staticmethod
    def normalize_intents(
        intents: Iterable[object],
    ) -> list[tuple[str, tuple[tuple[str, Any], ...]]]:
        items: list[tuple[str, tuple[tuple[str, Any], ...]]] = []
        for intent in intents:
            name = type(intent).__name__
            raw = {}
            try:
                raw = dict(vars(intent))
            except Exception:
                raw = {}
            norm = {k: _normalize_value(v) for k, v in raw.items() if not str(k).startswith("_")}
            items.append((name, tuple(sorted(norm.items()))))
        items.sort(key=lambda x: (x[0], x[1]))
        return items

    @staticmethod
    def normalize_view_model(vm: HipViewModel) -> dict[str, Any]:
        try:
            data = asdict(vm)
        except Exception:
            data = dict(vars(vm))
        norm = _normalize_value(data)
        try:
            if "age_ms" in norm:
                norm["age_ms"] = None if norm["age_ms"] is None else int(norm["age_ms"])
            if "lifetick_age" in norm:
                norm["lifetick_age"] = (
                    None if norm["lifetick_age"] is None else int(norm["lifetick_age"])
                )
        except Exception:
            pass
        return norm

    def _compute_param_ui_state(
        self, *, edit_active: bool, edit_group: str, estate: str
    ) -> HipParamUiState:
        groups = ("pos", "vel", "filter", "guider")
        state_groups: dict[str, HipParamGroup] = {}
        estate = str(estate or "").upper()
        edits_allowed = estate not in ("ARMED", "READY")

        if edit_active:
            for g in groups:
                if g == edit_group:
                    busy = self._param_txn.is_group_busy(g)
                    buttons = HipParamButtons(
                        edit_enabled=False if edits_allowed else False,
                        write_enabled=bool((not busy) and edits_allowed),
                        cancel_enabled=bool(not busy),
                    )
                    if busy:
                        buttons = HipParamButtons(
                            edit_enabled=False, write_enabled=False, cancel_enabled=False
                        )
                    state_groups[g] = HipParamGroup(fields_enabled=bool(not busy), buttons=buttons)
                else:
                    state_groups[g] = HipParamGroup(
                        fields_enabled=False,
                        buttons=HipParamButtons(
                            edit_enabled=False, write_enabled=False, cancel_enabled=False
                        ),
                    )
            return HipParamUiState(
                modal_lock_active=True,
                modal_lock_group=str(edit_group or ""),
                groups=state_groups,
            )

        for g in groups:
            busy = self._param_txn.is_group_busy(g)
            if busy:
                buttons = HipParamButtons(
                    edit_enabled=False, write_enabled=False, cancel_enabled=False
                )
            else:
                buttons = HipParamButtons(
                    edit_enabled=bool(edits_allowed),
                    write_enabled=False,
                    cancel_enabled=False,
                )
            state_groups[g] = HipParamGroup(fields_enabled=False, buttons=buttons)

        return HipParamUiState(
            modal_lock_active=False,
            modal_lock_group="",
            groups=state_groups,
        )

    @staticmethod
    def _get_lifetick_age(*, snap: TelemetrySnapshot, axis_id: str) -> int | None:
        axes = getattr(snap, "axes", None)
        if not isinstance(axes, dict):
            return None
        ax = axes.get(axis_id)
        if ax is None:
            return None
        try:
            return int(getattr(ax, "lifetick_age", 0) or 0)
        except Exception:
            return None

    @staticmethod
    def _compute_lifetick_echo_intents(
        *,
        snap: TelemetrySnapshot,
        hip_id: str,
        selected_axis: str = "",
        last_lifetick_echo_sent: dict[str, int],
    ) -> tuple[list[Intent], dict[str, int]]:
        axes = getattr(snap, "axes", None)
        if not isinstance(axes, dict) or not axes:
            return [], last_lifetick_echo_sent

        axis_id = str(selected_axis or "").strip()
        if not axis_id:
            return [], last_lifetick_echo_sent
        ax = axes.get(axis_id)
        if ax is None:
            return [], last_lifetick_echo_sent
        try:
            v = int(getattr(ax, "device_tick", 0)) & 0xFFFF
        except Exception:
            v = 0

        prev = last_lifetick_echo_sent.get(axis_id)
        if prev is not None and int(prev) == v:
            return [], last_lifetick_echo_sent

        last_lifetick_echo_sent[axis_id] = v
        intents: list[Intent] = [EchoLifeTick(axis_id=axis_id, value=v, hip_id=str(hip_id or ""))]
        return intents, last_lifetick_echo_sent


def _normalize_value(val: Any) -> Any:
    if isinstance(val, float):
        return round(val, 6)
    if isinstance(val, (int, str, bool)) or val is None:
        return val
    if isinstance(val, dict):
        return {
            str(k): _normalize_value(v) for k, v in sorted(val.items(), key=lambda x: str(x[0]))
        }
    if isinstance(val, set):
        return [_normalize_value(v) for v in sorted(val, key=lambda x: str(x))]
    if isinstance(val, (list, tuple)):
        return [_normalize_value(v) for v in val]
    try:
        return str(val)
    except Exception:
        return "<unrepr>"
