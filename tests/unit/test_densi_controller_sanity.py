from __future__ import annotations

from steuerung3d.apps.yellow.controllers.densi_controller import DenSiController


def test_densi_controller_static_helpers_are_callable_on_instance() -> None:
    """Guards against accidental removal of @staticmethod decorators.

    If a helper like _reset_able_from_estop_word loses its @staticmethod,
    calling it as self._reset_able_from_estop_word(...) will TypeError.
    We create an uninitialized instance (no Qt needed) and call the helpers.
    """
    dc = object.__new__(DenSiController)
    assert isinstance(dc._reset_able_from_estop_word(0), bool)
    assert isinstance(dc._ready_from_estop_word(0), bool)
