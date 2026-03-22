from __future__ import annotations

from types import SimpleNamespace

from qt_panda_spike.backends.base import PickReport
from qt_panda_spike.backends.native_embed import NativeEmbedBackend


class _Pointer:
    def __init__(self, x: int, y: int) -> None:
        self._x = x
        self._y = y

    def get_x(self) -> int:
        return self._x

    def get_y(self) -> int:
        return self._y


class _Window:
    def __init__(self, x: int, y: int, width: int = 800, height: int = 600) -> None:
        self._pointer = _Pointer(x, y)
        self._width = width
        self._height = height

    def get_pointer(self, index: int) -> _Pointer:
        assert index == 0
        return self._pointer

    def get_x_size(self) -> int:
        return self._width

    def get_y_size(self) -> int:
        return self._height


class _MouseWatcher:
    def __init__(self, *, has_mouse: bool, left_down: bool, right_down: bool) -> None:
        self._has_mouse = has_mouse
        self._left_down = left_down
        self._right_down = right_down

    def has_mouse(self) -> bool:
        return self._has_mouse

    def is_button_down(self, button: str) -> bool:
        if button == 'mouse1':
            return self._left_down
        if button == 'mouse3':
            return self._right_down
        return False


class _MouseButton:
    @staticmethod
    def one() -> str:
        return 'mouse1'

    @staticmethod
    def three() -> str:
        return 'mouse3'


def test_pick_from_pointer_enqueues_status_message() -> None:
    backend = NativeEmbedBackend()
    backend._base = SimpleNamespace(win=_Window(120, 80, width=640, height=480))
    backend.pick = lambda request: PickReport(status_text=f'Pick at {request.image_x:.0f},{request.image_y:.0f}', debug_record={})

    backend._pick_from_pointer(120, 80)

    assert backend.drain_status_messages() == ['Pick at 120,80']
    assert backend.drain_status_messages() == []


def test_poll_native_input_orbits_and_picks(monkeypatch) -> None:
    import sys

    panda3d_core = SimpleNamespace(MouseButton=_MouseButton)
    monkeypatch.setitem(sys.modules, 'panda3d', SimpleNamespace(core=panda3d_core))
    monkeypatch.setitem(sys.modules, 'panda3d.core', panda3d_core)

    backend = NativeEmbedBackend()
    orbit_calls: list[tuple[int, int]] = []
    pick_calls: list[tuple[int, int]] = []
    backend.orbit = lambda dx, dy: orbit_calls.append((int(dx), int(dy)))
    backend._pick_from_pointer = lambda x, y: pick_calls.append((x, y))

    backend._base = SimpleNamespace(
        win=_Window(100, 120),
        mouseWatcherNode=_MouseWatcher(has_mouse=True, left_down=True, right_down=False),
    )
    backend._left_drag_active = True
    backend._last_pointer = (90, 105)

    backend._poll_native_input()

    assert orbit_calls == [(10, 15)]
    assert backend._last_pointer == (100, 120)

    backend._base = SimpleNamespace(
        win=_Window(130, 140),
        mouseWatcherNode=_MouseWatcher(has_mouse=True, left_down=False, right_down=True),
    )
    backend._last_right_down = False

    backend._poll_native_input()

    assert pick_calls == [(130, 140)]
    assert backend._last_right_down is True
