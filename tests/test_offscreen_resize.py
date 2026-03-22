from types import SimpleNamespace

from qt_panda_spike.backends.offscreen import OffscreenBackend


class _Lens:
    def __init__(self) -> None:
        self.aspect_values: list[float] = []

    def set_aspect_ratio(self, value: float) -> None:
        self.aspect_values.append(value)


class _Buffer:
    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.requested_sizes: list[tuple[int, int]] = []
        self.set_sizes: list[tuple[int, int]] = []

    def request_properties(self, props: object) -> None:
        self.requested_sizes.append((int(props._width), int(props._height)))

    def set_size(self, width: int, height: int) -> None:
        self.set_sizes.append((int(width), int(height)))

    def get_x_size(self) -> int:
        return self.width

    def get_y_size(self) -> int:
        return self.height


def test_desired_buffer_size_tracks_device_pixel_ratio() -> None:
    widget = SimpleNamespace(devicePixelRatioF=lambda: 1.5)

    assert OffscreenBackend._desired_buffer_size(1280, 800, widget) == (1920, 1200)


def test_desired_buffer_size_falls_back_to_safe_defaults() -> None:
    assert OffscreenBackend._desired_buffer_size(0, 0, None) == (1, 1)


def test_sync_actual_buffer_size_updates_cached_size_and_lens() -> None:
    backend = OffscreenBackend()
    buffer = _Buffer(1600, 900)
    lens = _Lens()

    backend._buffer = buffer
    backend._lens = lens
    backend._buffer_size = (960, 540)
    backend._pending_buffer_size = (1600, 900)

    backend._sync_actual_buffer_size()

    assert backend._buffer_size == (1600, 900)
    assert backend._pending_buffer_size is None
    assert lens.aspect_values[-1] == 1600 / 900


def test_resize_defers_request_until_first_frame_and_debounce(monkeypatch) -> None:
    backend = OffscreenBackend()
    buffer = _Buffer(960, 540)
    backend._buffer = buffer
    backend._host_widget = SimpleNamespace(devicePixelRatioF=lambda: 1.25)
    backend._buffer_size = (960, 540)

    class _WindowProperties:
        def __init__(self) -> None:
            self._width = 0
            self._height = 0

        def set_size(self, width: int, height: int) -> None:
            self._width = width
            self._height = height

    import sys

    panda3d_core = SimpleNamespace(WindowProperties=_WindowProperties)
    monkeypatch.setitem(sys.modules, 'panda3d', SimpleNamespace(core=panda3d_core))
    monkeypatch.setitem(sys.modules, 'panda3d.core', panda3d_core)

    now = {'value': 10.0}
    monkeypatch.setattr('qt_panda_spike.backends.offscreen.time.monotonic', lambda: now['value'])

    backend.resize(1280, 800)

    assert buffer.requested_sizes == []
    assert buffer.set_sizes == []
    assert backend._pending_buffer_size == (1600, 1000)

    backend._has_seen_frame = True
    backend._apply_pending_resize_if_ready()
    assert buffer.requested_sizes == []

    now['value'] = 10.3
    backend._apply_pending_resize_if_ready()

    assert buffer.requested_sizes == [(1600, 1000)]
    assert backend._requested_buffer_size == (1600, 1000)


def test_resize_falls_back_to_set_size_when_request_properties_is_missing() -> None:
    backend = OffscreenBackend()

    class _SetSizeOnlyBuffer:
        def __init__(self) -> None:
            self.calls: list[tuple[int, int]] = []

        def set_size(self, width: int, height: int) -> None:
            self.calls.append((int(width), int(height)))

        def get_x_size(self) -> int:
            return 960

        def get_y_size(self) -> int:
            return 540

    buffer = _SetSizeOnlyBuffer()
    backend._buffer = buffer
    backend._pending_buffer_size = (1600, 1000)
    backend._buffer_size = (960, 540)
    backend._has_seen_frame = True

    backend._apply_pending_resize_if_ready()

    assert buffer.calls == [(1600, 1000)]
    assert backend._requested_buffer_size == (1600, 1000)


def test_resize_recreates_buffer_when_set_size_raises() -> None:
    backend = OffscreenBackend()

    class _FailingSetSizeBuffer:
        def set_size(self, width: int, height: int) -> None:
            raise AssertionError("Cannot resize buffer unless it is created with BF_resizeable flag")

        def get_x_size(self) -> int:
            return 960

        def get_y_size(self) -> int:
            return 540

    calls: list[tuple[int, int]] = []

    def _recreate(requested: tuple[int, int]) -> bool:
        calls.append(requested)
        return True

    backend._buffer = _FailingSetSizeBuffer()
    backend._pending_buffer_size = (1600, 1000)
    backend._buffer_size = (960, 540)
    backend._has_seen_frame = True
    backend._recreate_offscreen_buffer = _recreate  # type: ignore[method-assign]

    backend._apply_pending_resize_if_ready()

    assert calls == [(1600, 1000)]
    assert backend._requested_buffer_size == (1600, 1000)


def test_resize_coalesces_to_latest_requested_size(monkeypatch) -> None:
    backend = OffscreenBackend()
    buffer = _Buffer(960, 540)
    backend._buffer = buffer
    backend._host_widget = SimpleNamespace(devicePixelRatioF=lambda: 1.0)
    backend._buffer_size = (960, 540)
    backend._has_seen_frame = True

    class _WindowProperties:
        def __init__(self) -> None:
            self._width = 0
            self._height = 0

        def set_size(self, width: int, height: int) -> None:
            self._width = width
            self._height = height

    import sys

    panda3d_core = SimpleNamespace(WindowProperties=_WindowProperties)
    monkeypatch.setitem(sys.modules, 'panda3d', SimpleNamespace(core=panda3d_core))
    monkeypatch.setitem(sys.modules, 'panda3d.core', panda3d_core)

    now = {'value': 20.0}
    monkeypatch.setattr('qt_panda_spike.backends.offscreen.time.monotonic', lambda: now['value'])

    backend.resize(1100, 700)
    now['value'] = 20.1
    backend.resize(1400, 900)
    now['value'] = 20.2
    backend.resize(1500, 1000)

    backend._apply_pending_resize_if_ready()
    assert buffer.requested_sizes == []

    now['value'] = 20.6
    backend._apply_pending_resize_if_ready()

    assert buffer.requested_sizes == [(1500, 1000)]
    assert backend._requested_buffer_size == (1500, 1000)
