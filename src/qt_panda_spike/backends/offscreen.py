from __future__ import annotations

import time
from typing import Any

from .base import FrameImage, PickReport, PickRequest, ViewportBackend
from ..scene.demo_scene import DOME_RADIUS, build_demo_scene
from ..scene.picking import Picker


class OffscreenBackend(ViewportBackend):
    def __init__(self, *, show_dome: bool = False, pick_debug: bool = False) -> None:
        self._show_dome = bool(show_dome)
        self._pick_debug = bool(pick_debug)
        self._base: Any | None = None
        self._buffer: Any | None = None
        self._texture: Any | None = None
        self._lens: Any | None = None
        self._picker: Picker | None = None
        self._scene_hit_marker: Any | None = None
        self._dome_hit_marker: Any | None = None
        self._last_frame: FrameImage | None = None
        self._started = False
        self._host_widget: Any | None = None
        self._buffer_size = (960, 540)
        self._pending_buffer_size: tuple[int, int] | None = None
        self._requested_buffer_size: tuple[int, int] | None = None
        self._has_seen_frame = False
        self._resize_debounce_s = 0.25
        self._pending_resize_deadline: float | None = None

    def start(self, host_widget: Any) -> None:
        if self._started:
            return

        from panda3d.core import GraphicsOutput, Texture, loadPrcFileData
        from direct.showbase.ShowBase import ShowBase

        loadPrcFileData("", "window-type offscreen")
        loadPrcFileData("", "audio-library-name null")

        base = ShowBase(windowType="offscreen")
        if base.win is None:
            raise RuntimeError("Could not open Panda3D offscreen window")

        self._host_widget = host_widget

        tex = Texture()
        base.win.add_render_texture(tex, GraphicsOutput.RTMCopyRam)
        base.disable_mouse()

        self._base = base
        self._buffer = base.win
        self._texture = tex
        self._lens = base.cam.node().get_lens()
        self._buffer_size = (
            max(1, int(base.win.get_x_size())),
            max(1, int(base.win.get_y_size())),
        )
        self._pending_buffer_size = self._desired_buffer_size(host_widget.width(), host_widget.height(), host_widget)
        if self._pending_buffer_size == self._buffer_size:
            self._pending_buffer_size = None
        self._requested_buffer_size = None
        self._has_seen_frame = False
        self._pending_resize_deadline = None
        self._pending_resize_deadline = self._deadline_from_now() if self._pending_buffer_size is not None else None
        self._set_camera_defaults()
        if self._lens is not None and self._buffer_size[1] > 0:
            self._lens.set_aspect_ratio(self._buffer_size[0] / self._buffer_size[1])
        build_demo_scene(base, show_dome=self._show_dome)
        self._picker = Picker(base, dome_radius=DOME_RADIUS, include_dome_hit=self._show_dome)
        if self._pick_debug:
            self._scene_hit_marker = self._create_hit_marker("scene_pick_marker", (1.0, 0.95, 0.15, 1.0), 0.12)
            self._dome_hit_marker = self._create_hit_marker("dome_pick_marker", (0.2, 0.95, 1.0, 1.0), 0.09)
        self._started = True

    def _set_camera_defaults(self) -> None:
        assert self._base is not None
        self._base.cam.set_pos(0.0, -14.0, 4.0)
        self._base.cam.look_at(0.0, 0.0, 0.5)

    def _create_hit_marker(self, name: str, color: tuple[float, float, float, float], scale: float) -> Any:
        assert self._base is not None
        from panda3d.core import BitMask32

        marker = self._base.loader.load_model("models/misc/sphere")
        marker.reparent_to(self._base.render)
        marker.set_name(name)
        marker.set_scale(scale)
        marker.set_color(*color)
        marker.set_collide_mask(BitMask32.all_off())
        marker.hide()
        return marker

    def step(self) -> None:
        if self._base is None or self._texture is None:
            return
        self._base.task_mgr.step()
        self._sync_actual_buffer_size()
        if self._texture.has_ram_image():
            data = bytes(self._texture.get_ram_image_as("RGBA"))
            self._last_frame = FrameImage(
                width=int(self._texture.get_x_size()),
                height=int(self._texture.get_y_size()),
                rgba_bytes=data,
            )
            self._has_seen_frame = True
        self._apply_pending_resize_if_ready()

    def resize(self, width: int, height: int) -> None:
        if self._buffer is None:
            return
        requested_size = self._desired_buffer_size(width, height, self._host_widget)
        if requested_size == self._buffer_size:
            self._pending_buffer_size = None
            self._requested_buffer_size = None
            self._pending_resize_deadline = None
            return
        self._pending_buffer_size = requested_size
        if self._requested_buffer_size != requested_size:
            self._requested_buffer_size = None
        self._pending_resize_deadline = self._deadline_from_now()

    def orbit(self, delta_x: float, delta_y: float) -> None:
        if self._base is None:
            return
        h = float(self._base.cam.get_h()) - (delta_x * 0.25)
        p = float(self._base.cam.get_p()) + (delta_y * 0.25)
        self._base.cam.set_hpr(h, max(-85.0, min(85.0, p)), 0.0)

    def zoom(self, wheel_delta: float) -> None:
        if self._base is None:
            return
        y = float(self._base.cam.get_y()) + (-wheel_delta * 0.002)
        self._base.cam.set_y(max(-40.0, min(-3.0, y)))

    def is_ready(self) -> bool:
        return self._last_frame is not None

    def latest_frame(self) -> FrameImage | None:
        return self._last_frame

    def pick(self, request: PickRequest) -> PickReport | None:
        if self._picker is None:
            return None
        hit = self._picker.pick(request.image_x, request.image_y, request.image_width, request.image_height)
        if hit is None:
            if self._scene_hit_marker is not None:
                self._scene_hit_marker.hide()
            if self._dome_hit_marker is not None:
                self._dome_hit_marker.hide()
            return PickReport(status_text="Pick: no hit", debug_record={})
        if self._scene_hit_marker is not None:
            point = hit.pick_trace.scene_hit_world
            if point is not None:
                self._scene_hit_marker.set_pos(point.x, point.y, point.z)
                self._scene_hit_marker.show()
            else:
                self._scene_hit_marker.hide()
        if self._dome_hit_marker is not None:
            point = hit.pick_trace.dome_hit_world
            if point is not None:
                self._dome_hit_marker.set_pos(point.x, point.y, point.z)
                self._dome_hit_marker.show()
            else:
                self._dome_hit_marker.hide()
        debug_record = {"scene": hit.to_record()} if self._pick_debug else {}
        return PickReport(status_text=hit.format_status(), debug_record=debug_record)

    def shutdown(self) -> None:
        if self._base is not None and self._base.win is not None:
            self._base.close_window(self._base.win)
        self._base = None
        self._buffer = None
        self._texture = None
        self._lens = None
        self._picker = None
        self._scene_hit_marker = None
        self._dome_hit_marker = None
        self._last_frame = None
        self._host_widget = None
        self._started = False
        self._pending_buffer_size = None
        self._requested_buffer_size = None
        self._has_seen_frame = False
        self._pending_resize_deadline = None

    @staticmethod
    def _desired_buffer_size(width: int, height: int, host_widget: Any | None) -> tuple[int, int]:
        pixel_ratio = 1.0
        if host_widget is not None:
            maybe_ratio = getattr(host_widget, "devicePixelRatioF", None)
            if callable(maybe_ratio):
                try:
                    pixel_ratio = float(maybe_ratio())
                except Exception:
                    pixel_ratio = 1.0
        safe_ratio = max(1.0, pixel_ratio)
        return (
            max(1, int(round(max(1, width) * safe_ratio))),
            max(1, int(round(max(1, height) * safe_ratio))),
        )

    def _deadline_from_now(self) -> float:
        return time.monotonic() + max(0.0, float(self._resize_debounce_s))


    def _apply_pending_resize_if_ready(self) -> None:
        if self._buffer is None or self._pending_buffer_size is None:
            return
        if self._pending_buffer_size == self._buffer_size:
            self._pending_buffer_size = None
            self._requested_buffer_size = None
            self._pending_resize_deadline = None
            return
        if not self._has_seen_frame:
            return
        if self._requested_buffer_size == self._pending_buffer_size:
            return
        if self._pending_resize_deadline is not None and time.monotonic() < self._pending_resize_deadline:
            return

        requested = self._pending_buffer_size
        if self._request_buffer_resize(requested):
            self._requested_buffer_size = requested
            self._pending_resize_deadline = None

    def _request_buffer_resize(self, requested_size: tuple[int, int]) -> bool:
        if self._buffer is None:
            return False

        request_properties = getattr(self._buffer, 'request_properties', None)
        if callable(request_properties):
            try:
                from panda3d.core import WindowProperties

                wp = WindowProperties()
                wp.set_size(*requested_size)
                request_properties(wp)
                return True
            except Exception:
                pass

        set_size = getattr(self._buffer, 'set_size', None)
        if callable(set_size):
            try:
                set_size(*requested_size)
                return True
            except Exception:
                pass

        return self._recreate_offscreen_buffer(requested_size)

    def _recreate_offscreen_buffer(self, requested_size: tuple[int, int]) -> bool:
        if self._base is None:
            return False

        open_window = getattr(self._base, 'openWindow', None)
        if not callable(open_window):
            return False

        old_buffer = self._buffer
        try:
            new_buffer = open_window(type='offscreen', keepCamera=True, makeCamera=False, size=requested_size)
        except Exception:
            return False
        if new_buffer is None:
            return False

        from panda3d.core import GraphicsOutput, Texture

        tex = Texture()
        new_buffer.add_render_texture(tex, GraphicsOutput.RTMCopyRam)
        self._buffer = new_buffer
        self._texture = tex
        self._last_frame = None
        self._has_seen_frame = False

        try:
            self._base.win = new_buffer
        except Exception:
            pass

        actual_size = (
            max(1, int(new_buffer.get_x_size())),
            max(1, int(new_buffer.get_y_size())),
        )
        self._buffer_size = actual_size
        if self._lens is not None and actual_size[1] > 0:
            self._lens.set_aspect_ratio(actual_size[0] / actual_size[1])
        if actual_size == requested_size:
            self._pending_buffer_size = None

        close_window = getattr(self._base, 'close_window', None)
        if callable(close_window) and old_buffer is not None and old_buffer is not new_buffer:
            try:
                close_window(old_buffer)
            except Exception:
                pass
        return True

    def _sync_actual_buffer_size(self) -> None:
        if self._buffer is None:
            return
        actual_width = int(self._buffer.get_x_size())
        actual_height = int(self._buffer.get_y_size())
        if actual_width <= 0 or actual_height <= 0:
            return
        actual_size = (actual_width, actual_height)
        if actual_size != self._buffer_size:
            self._buffer_size = actual_size
        if self._pending_buffer_size == actual_size:
            self._pending_buffer_size = None
            self._pending_resize_deadline = None
        if self._lens is not None and actual_height > 0:
            self._lens.set_aspect_ratio(actual_width / actual_height)
