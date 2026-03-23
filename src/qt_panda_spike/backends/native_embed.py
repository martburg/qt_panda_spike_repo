# pyright: reportMissingImports=false, reportMissingTypeStubs=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownParameterType=false, reportAttributeAccessIssue=false, reportCallIssue=false, reportUntypedBaseClass=false
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from qt_panda_spike.backends.base import PickReport, PickRequest, ViewportBackend
from qt_panda_spike.scene.picking import Picker

from qt_panda_spike.scene.demo_scene import DOME_RADIUS, build_demo_scene

if TYPE_CHECKING:
    from panda3d.core import WindowProperties


class NativeEmbedBackend(ViewportBackend):
    def __init__(self, *, show_dome: bool = False, pick_debug: bool = False) -> None:
        self._show_dome = bool(show_dome)
        self._pick_debug = bool(pick_debug)
        self._base: Any | None = None
        self._lens: Any | None = None
        self._picker: Picker | None = None
        self._scene_hit_marker: Any | None = None
        self._dome_hit_marker: Any | None = None
        self._started = False
        self._left_drag_active = False
        self._last_pointer: tuple[int, int] | None = None
        self._last_right_down = False
        self._pending_status_messages: list[str] = []
        self._orbit_target: tuple[float, float, float] = (0.0, 0.0, 0.9)
        self._orbit_heading_deg = 0.0
        self._orbit_pitch_deg = 18.0
        self._orbit_distance = 13.5

    def start(self, host_widget: Any) -> None:
        if self._started:
            return

        from direct.showbase.ShowBase import ShowBase
        from panda3d.core import NativeWindowHandle, WindowProperties, loadPrcFileData

        loadPrcFileData("", "window-type none")
        loadPrcFileData("", "audio-library-name null")

        base = ShowBase(windowType="none")
        wp = WindowProperties()
        wp.set_parent_window(NativeWindowHandle.make_int(int(host_widget.winId())))
        wp.set_origin(0, 0)
        wp.set_size(max(1, host_widget.width()), max(1, host_widget.height()))
        wp.set_undecorated(True)

        ok = base.open_default_window(props=wp)
        if not ok or base.win is None:
            raise RuntimeError("Could not open embedded Panda3D window")
        if base.cam is None:
            raise RuntimeError("Panda3D camera was not created")

        base.disable_mouse()
        self._base = base
        self._lens = base.cam.node().get_lens()
        build_demo_scene(base, show_dome=self._show_dome)
        self._picker = Picker(base, dome_radius=DOME_RADIUS, include_dome_hit=self._show_dome)
        if self._pick_debug:
            self._scene_hit_marker = self._create_hit_marker(
                "scene_pick_marker", (1.0, 0.95, 0.15, 1.0), 0.12
            )
            self._dome_hit_marker = self._create_hit_marker(
                "dome_pick_marker", (0.2, 0.95, 1.0, 1.0), 0.09
            )
        self._apply_camera_pose()
        self.resize(host_widget.width(), host_widget.height())
        base.accept("wheel_up", self._on_wheel_up)
        base.accept("wheel_down", self._on_wheel_down)
        self._started = True

    def _apply_camera_pose(self) -> None:
        if self._base is None:
            return
        import math

        focus_x, focus_y, focus_z = self._orbit_target
        heading_rad = math.radians(self._orbit_heading_deg)
        pitch_rad = math.radians(self._orbit_pitch_deg)
        horizontal = self._orbit_distance * math.cos(pitch_rad)
        x = focus_x + (horizontal * math.sin(heading_rad))
        y = focus_y - (horizontal * math.cos(heading_rad))
        z = focus_z + (self._orbit_distance * math.sin(pitch_rad))
        self._base.cam.set_pos(x, y, z)
        self._base.cam.look_at(focus_x, focus_y, focus_z)

    def _create_hit_marker(
        self, name: str, color: tuple[float, float, float, float], scale: float
    ) -> Any:
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
        if self._base is not None:
            self._base.task_mgr.step()
            self._poll_native_input()

    def resize(self, width: int, height: int) -> None:
        if self._lens is not None and width > 0 and height > 0:
            self._lens.set_aspect_ratio(width / height)
        if self._base is None or self._base.win is None:
            return
        try:
            from panda3d.core import WindowProperties

            wp: WindowProperties = WindowProperties()
            wp.set_size(max(1, int(width)), max(1, int(height)))
            request_properties = getattr(self._base.win, "request_properties", None)
            if callable(request_properties):
                request_properties(wp)
        except Exception:
            pass

    def orbit(self, delta_x: float, delta_y: float) -> None:
        if self._base is None:
            return
        self._orbit_heading_deg -= float(delta_x) * 0.35
        self._orbit_pitch_deg = max(
            -80.0,
            min(80.0, self._orbit_pitch_deg + (float(delta_y) * 0.25)),
        )
        self._apply_camera_pose()

    def zoom(self, wheel_delta: float) -> None:
        if self._base is None:
            return
        self._orbit_distance = max(
            3.0,
            min(40.0, self._orbit_distance + (-float(wheel_delta) * 0.01)),
        )
        self._apply_camera_pose()

    def pick(self, request: PickRequest) -> PickReport | None:
        picker = self._picker
        if picker is None:
            return None
        hit = picker.pick(
            request.image_x,
            request.image_y,
            request.image_width,
            request.image_height,
        )
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
        debug_record: dict[str, object] = {}
        if self._pick_debug:
            debug_record = {"scene": hit.to_record()}
        return PickReport(status_text=hit.format_status(), debug_record=debug_record)

    def is_ready(self) -> bool:
        return self._started and self._base is not None and self._base.win is not None

    def drain_status_messages(self) -> list[str]:
        messages = list(self._pending_status_messages)
        self._pending_status_messages.clear()
        return messages

    def _poll_native_input(self) -> None:
        if self._base is None or self._base.win is None:
            return
        mouse_watcher = getattr(self._base, "mouseWatcherNode", None)
        if mouse_watcher is None or not mouse_watcher.has_mouse():
            self._left_drag_active = False
            self._last_pointer = None
            self._last_right_down = False
            return

        pointer = self._base.win.get_pointer(0)
        pointer_x = int(pointer.get_x())
        pointer_y = int(pointer.get_y())

        from panda3d.core import MouseButton

        left_down = bool(mouse_watcher.is_button_down(MouseButton.one()))
        right_down = bool(mouse_watcher.is_button_down(MouseButton.three()))

        if left_down:
            if self._left_drag_active and self._last_pointer is not None:
                last_x, last_y = self._last_pointer
                self.orbit(pointer_x - last_x, pointer_y - last_y)
            self._left_drag_active = True
            self._last_pointer = (pointer_x, pointer_y)
        else:
            self._left_drag_active = False
            self._last_pointer = None

        if right_down and not self._last_right_down:
            self._pick_from_pointer(pointer_x=pointer_x, pointer_y=pointer_y)
        self._last_right_down = right_down

    def _pick_from_pointer(self, pointer_x: int, pointer_y: int) -> None:
        if self._base is None or self._base.win is None:
            return
        width = float(max(1, self._base.win.get_x_size()))
        height = float(max(1, self._base.win.get_y_size()))
        report = self.pick(
            PickRequest(
                widget_x=float(pointer_x),
                widget_y=float(pointer_y),
                widget_width=width,
                widget_height=height,
                display_x=0.0,
                display_y=0.0,
                display_width=width,
                display_height=height,
                image_x=float(pointer_x),
                image_y=float(pointer_y),
                image_width=width,
                image_height=height,
            )
        )
        if report is not None:
            self._pending_status_messages.append(report.status_text)

    def _on_wheel_up(self) -> None:
        self.zoom(120.0)

    def _on_wheel_down(self) -> None:
        self.zoom(-120.0)

    def shutdown(self) -> None:
        if self._base is not None and self._base.win is not None:
            self._base.close_window(self._base.win)
        self._base = None
        self._lens = None
        self._picker = None
        self._scene_hit_marker = None
        self._dome_hit_marker = None
        self._started = False
        self._left_drag_active = False
        self._last_pointer = None
        self._last_right_down = False
        self._pending_status_messages.clear()
