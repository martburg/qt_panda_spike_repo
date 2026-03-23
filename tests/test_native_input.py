# pyright: reportMissingImports=false, reportMissingTypeStubs=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownParameterType=false, reportAttributeAccessIssue=false, reportCallIssue=false
from __future__ import annotations

from types import MethodType, SimpleNamespace
from typing import Any

import pytest
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
        self.requested_sizes: list[tuple[int, int]] = []

    def get_pointer(self, index: int) -> _Pointer:
        assert index == 0
        return self._pointer

    def get_x_size(self) -> int:
        return self._width

    def get_y_size(self) -> int:
        return self._height

    def request_properties(self, props: object) -> None:
        width = getattr(props, "_width", None)
        height = getattr(props, "_height", None)
        if width is not None and height is not None:
            self.requested_sizes.append((int(width), int(height)))


class _MouseWatcher:
    def __init__(self, *, has_mouse: bool, left_down: bool, right_down: bool) -> None:
        self._has_mouse = has_mouse
        self._left_down = left_down
        self._right_down = right_down

    def has_mouse(self) -> bool:
        return self._has_mouse

    def is_button_down(self, button: str) -> bool:
        if button == "mouse1":
            return self._left_down
        if button == "mouse3":
            return self._right_down
        return False


class _MouseButton:
    @staticmethod
    def one() -> str:
        return "mouse1"

    @staticmethod
    def three() -> str:
        return "mouse3"


class _WindowProperties:
    def __init__(self) -> None:
        self._width = 0
        self._height = 0

    def set_size(self, width: int, height: int) -> None:
        self._width = width
        self._height = height


class _Lens:
    def __init__(self) -> None:
        self.aspect_values: list[float] = []

    def set_aspect_ratio(self, value: float) -> None:
        self.aspect_values.append(value)


class _Camera:
    def __init__(self) -> None:
        self.positions: list[tuple[float, float, float]] = []
        self.look_ats: list[tuple[float, float, float]] = []
        self.hprs: list[tuple[float, float, float]] = []
        self._y = -14.0
        self._h = 0.0
        self._p = 0.0

    def set_pos(self, x: float, y: float, z: float) -> None:
        self.positions.append((x, y, z))

    def look_at(self, x: float, y: float, z: float) -> None:
        self.look_ats.append((x, y, z))

    def get_y(self) -> float:
        return self._y

    def set_y(self, value: float) -> None:
        self._y = value

    def get_h(self) -> float:
        return self._h

    def get_p(self) -> float:
        return self._p

    def set_hpr(self, h: float, p: float, r: float) -> None:
        self._h = h
        self._p = p
        self.hprs.append((h, p, r))


def test_pick_from_pointer_enqueues_status_message() -> None:
    backend = NativeEmbedBackend()
    backend._base = SimpleNamespace(win=_Window(120, 80, width=640, height=480))

    def _pick_impl(self: NativeEmbedBackend, request: Any) -> PickReport:
        req = request
        return PickReport(
            status_text=(f"Pick at {req.image_x:.0f},{req.image_y:.0f}"),
            debug_record={},
        )

    backend.pick = MethodType(_pick_impl, backend)

    backend._pick_from_pointer(pointer_x=120, pointer_y=80)

    assert backend.drain_status_messages() == ["Pick at 120,80"]
    assert backend.drain_status_messages() == []


def test_poll_native_input_orbits_and_picks(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys

    panda3d_core = SimpleNamespace(MouseButton=_MouseButton)
    monkeypatch.setitem(sys.modules, "panda3d", SimpleNamespace(core=panda3d_core))
    monkeypatch.setitem(sys.modules, "panda3d.core", panda3d_core)

    backend = NativeEmbedBackend()
    orbit_calls: list[tuple[int, int]] = []
    pick_calls: list[tuple[int, int]] = []

    def _orbit_impl(self: NativeEmbedBackend, delta_x: float, delta_y: float) -> None:
        orbit_calls.append((int(delta_x), int(delta_y)))

    def _pick_from_pointer_impl(self: NativeEmbedBackend, pointer_x: int, pointer_y: int) -> None:
        pick_calls.append((pointer_x, pointer_y))

    backend.orbit = MethodType(_orbit_impl, backend)
    backend._pick_from_pointer = MethodType(_pick_from_pointer_impl, backend)

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


def test_resize_updates_lens_and_may_request_native_window_resize(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sys

    panda3d_core = SimpleNamespace(WindowProperties=_WindowProperties)
    monkeypatch.setitem(sys.modules, "panda3d", SimpleNamespace(core=panda3d_core))
    monkeypatch.setitem(sys.modules, "panda3d.core", panda3d_core)

    backend = NativeEmbedBackend()
    lens = _Lens()
    window = _Window(0, 0)
    backend._lens = lens
    backend._base = SimpleNamespace(win=window)

    backend.resize(1280, 720)

    assert lens.aspect_values[-1] == 1280 / 720
    assert window.requested_sizes in ([], [(1280, 720)])


def test_zoom_and_orbit_update_native_camera() -> None:
    backend = NativeEmbedBackend()
    camera = _Camera()
    backend._base = SimpleNamespace(cam=camera)

    backend.zoom(120.0)
    backend.orbit(20.0, -10.0)

    changed_zoom = bool(camera.positions) or camera.get_y() != -14.0
    changed_orbit = bool(camera.look_ats) or bool(camera.hprs)
    assert changed_zoom is True
    assert changed_orbit is True
