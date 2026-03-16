from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

pytestmark = pytest.mark.ui

from steuerung3d.apps.yellow.controllers.densi_controller import DenSiController
from steuerung3d.apps.yellow.engines.densi.inputs import DensiEstopToggle, DensiUiInputs


def test_densi_controller_static_helpers_are_callable_on_instance() -> None:
    """Guards against accidental removal of @staticmethod decorators.

    If a helper like _reset_able_from_estop_word loses its @staticmethod,
    calling it as self._reset_able_from_estop_word(...) will TypeError.
    """
    dc = object.__new__(DenSiController)
    assert isinstance(dc._reset_able_from_estop_word(0), bool)
    assert isinstance(dc._ready_from_estop_word(0), bool)


def test_densi_controller_merge_ui_inputs_preserves_remote_and_local_actions() -> None:
    remote = DensiUiInputs(
        es_start_clicked=True, estop_bit_toggles=[DensiEstopToggle(key="taster", checked=True)]
    )
    local = DensiUiInputs(diag_resync_clicked=True, estop_reset_clicked=True)

    merged = DenSiController._merge_ui_inputs(remote, local)

    assert merged.es_start_clicked is True
    assert merged.estop_reset_clicked is True
    assert merged.diag_resync_clicked is True
    assert merged.estop_bit_toggles == [DensiEstopToggle(key="taster", checked=True)]
