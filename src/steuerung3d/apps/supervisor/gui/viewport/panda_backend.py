# pyright: reportMissingImports=false, reportMissingTypeStubs=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownParameterType=false, reportUntypedBaseClass=false, reportOptionalMemberAccess=false, reportAttributeAccessIssue=false, reportCallIssue=false
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from steuerung3d.rig.scene.two_axis_head_snapshot import SceneSnapshot

from .selection_bridge import RawPickResult


@dataclass(frozen=True)
class _QueuedStatus:
    text: str


class PandaViewportBackend:
    """Native Panda3D child-window backend for the supervisor viewport.

    This slice intentionally uses a tiny generic demo scene so we can focus on
    startup visibility, resize, orbit, zoom, picking, and overlay behavior
    without coupling to the current rig geometry yet.
    """

    def __init__(self) -> None:
        self._base: Any | None = None
        self._host_widget: Any | None = None
        self._lens: Any | None = None
        self._picker_ray: Any | None = None
        self._picker_node: Any | None = None
        self._picker_queue: Any | None = None
        self._picker_traverser: Any | None = None
        self._pickable_mask_bit = 17
        self._started = False
        self._ready = False
        self._last_pointer: tuple[int, int] | None = None
        self._left_drag_active = False
        self._last_right_down = False
        self._orbit_target = (0.0, 0.0, 0.9)
        self._orbit_heading_deg = 0.0
        self._orbit_pitch_deg = 18.0
        self._orbit_distance = 13.5
        self._status_queue: list[_QueuedStatus] = []
        self._pick_queue: list[RawPickResult] = []
        self._scene_snapshot: SceneSnapshot | None = None
        self._requested_size: tuple[int, int] | None = None
        self._resize_retry_frames = 0

    def start(self, host_widget: Any) -> None:
        if self._started:
            return

        from direct.showbase.ShowBase import ShowBase
        from panda3d.core import NativeWindowHandle, WindowProperties, loadPrcFileData

        loadPrcFileData("", "window-type none")
        loadPrcFileData("", "audio-library-name null")

        base = ShowBase(windowType="none")
        props = WindowProperties()
        props.set_parent_window(NativeWindowHandle.make_int(int(host_widget.winId())))
        props.set_origin(0, 0)
        props.set_size(max(1, int(host_widget.width())), max(1, int(host_widget.height())))
        props.set_undecorated(True)

        ok = base.open_default_window(props=props)
        if not ok or base.win is None or base.cam is None:
            raise RuntimeError("Could not open embedded Panda3D window")

        base.disable_mouse()
        self._base = base
        self._host_widget = host_widget
        self._lens = base.cam.node().get_lens()
        self._build_demo_scene()
        self._setup_picking()
        self._apply_camera_pose()
        self.resize(int(host_widget.width()), int(host_widget.height()))
        base.accept("wheel_up", self._on_wheel_up)
        base.accept("wheel_down", self._on_wheel_down)
        self._started = True
        self._ready = True
        self._status_queue.append(_QueuedStatus("Panda viewport ready"))

    def apply_scene_snapshot(self, scene: SceneSnapshot | None) -> None:
        self._scene_snapshot = scene
        machine_id = "none" if scene is None else str(scene.machine_id or "") or "anonymous"
        self._status_queue.append(_QueuedStatus(f"Scene snapshot received | machine={machine_id}"))

    def step(self) -> None:
        if self._base is None:
            return
        self._base.task_mgr.step()
        self._poll_native_input()
        self._drain_resize_retries()

    def resize(self, width: int, height: int) -> None:
        self._requested_size = (max(1, int(width)), max(1, int(height)))
        self._resize_retry_frames = 6
        self._request_window_size(force=True)

    def _request_window_size(self, *, force: bool) -> None:
        if self._base is None or self._base.win is None or self._requested_size is None:
            return
        width, height = self._requested_size
        if self._lens is not None:
            self._lens.set_aspect_ratio(width / height)
        try:
            from panda3d.core import WindowProperties

            props = WindowProperties()
            props.set_origin(0, 0)
            props.set_size(width, height)
            request_properties = getattr(self._base.win, "request_properties", None)
            if callable(request_properties):
                request_properties(props)
            graphics_engine = getattr(self._base, "graphicsEngine", None)
            render_frame = getattr(graphics_engine, "render_frame", None)
            if callable(render_frame):
                render_frame()
        except Exception:
            if force:
                self._status_queue.append(
                    _QueuedStatus("Resize request fell back to lens aspect only")
                )

    def _drain_resize_retries(self) -> None:
        if self._resize_retry_frames <= 0:
            return
        self._request_window_size(force=False)
        self._resize_retry_frames -= 1

    def is_ready(self) -> bool:
        return self._ready

    def shutdown(self) -> None:
        if self._base is not None and self._base.win is not None:
            self._base.close_window(self._base.win)
        self._base = None
        self._host_widget = None
        self._lens = None
        self._picker_ray = None
        self._picker_node = None
        self._picker_queue = None
        self._picker_traverser = None
        self._started = False
        self._ready = False
        self._last_pointer = None
        self._left_drag_active = False
        self._last_right_down = False
        self._status_queue.clear()
        self._pick_queue.clear()
        self._requested_size = None
        self._resize_retry_frames = 0

    def drain_status_messages(self) -> list[str]:
        messages = [item.text for item in self._status_queue]
        self._status_queue.clear()
        return messages

    def drain_pick_results(self) -> list[RawPickResult]:
        results = list(self._pick_queue)
        self._pick_queue.clear()
        return results

    def _build_demo_scene(self) -> None:
        assert self._base is not None
        from panda3d.core import CardMaker, LineSegs, NodePath, Vec4

        render = self._base.render

        axes = LineSegs("axes")
        axes.set_thickness(2.0)
        axes.set_color(1.0, 0.2, 0.2, 1.0)
        axes.move_to(0, 0, 0)
        axes.draw_to(3, 0, 0)
        axes.set_color(0.2, 1.0, 0.2, 1.0)
        axes.move_to(0, 0, 0)
        axes.draw_to(0, 3, 0)
        axes.set_color(0.2, 0.45, 1.0, 1.0)
        axes.move_to(0, 0, 0)
        axes.draw_to(0, 0, 3)
        NodePath(axes.create()).reparent_to(render)

        grid = LineSegs("ground_grid")
        grid.set_color(0.35, 0.35, 0.4, 1.0)
        grid.set_thickness(1.0)
        for index in range(-6, 7):
            grid.move_to(index, -6, 0.0)
            grid.draw_to(index, 6, 0.0)
            grid.move_to(-6, index, 0.0)
            grid.draw_to(6, index, 0.0)
        NodePath(grid.create()).reparent_to(render)

        card = CardMaker("ground")
        card.set_frame(-6, 6, -6, 6)
        ground = render.attach_new_node(card.generate())
        ground.set_p(-90)
        ground.set_z(-0.01)
        ground.set_color(Vec4(0.15, 0.15, 0.18, 1.0))
        self._make_pickable(ground, "ground", object_kind="surface")

        sphere_model = self._base.loader.load_model("models/misc/sphere")

        def add_node(
            name: str,
            *,
            pos: tuple[float, float, float],
            scale: tuple[float, float, float] | float,
            color: tuple[float, float, float, float],
            object_kind: str = "node",
        ) -> None:
            np = sphere_model.copy_to(render)
            np.set_name(name)
            np.set_pos(*pos)
            if isinstance(scale, tuple):
                np.set_scale(*scale)
            else:
                np.set_scale(scale)
            np.set_color(*color)
            self._make_pickable(np, name, object_kind=object_kind)

        add_node("center_node", pos=(0.0, 0.0, 0.8), scale=0.45, color=(0.95, 0.8, 0.15, 1.0))
        add_node("left_node", pos=(-2.6, 2.1, 1.0), scale=0.55, color=(0.9, 0.2, 0.2, 1.0))
        add_node("right_node", pos=(2.8, 2.4, 1.15), scale=0.6, color=(0.2, 0.45, 0.95, 1.0))
        add_node("rear_node", pos=(0.5, -2.8, 1.5), scale=0.5, color=(0.2, 0.9, 0.35, 1.0))
        add_node(
            "tower_node",
            pos=(-0.5, 3.8, 1.7),
            scale=(0.35, 0.35, 1.6),
            color=(0.9, 0.55, 0.2, 1.0),
            object_kind="marker",
        )

    def _make_pickable(self, node: Any, name: str, *, object_kind: str) -> None:
        from panda3d.core import BitMask32

        mask = BitMask32.bit(self._pickable_mask_bit)
        node.set_name(name)
        node.set_tag("pick_name", name)
        node.set_tag("pick_kind", object_kind)
        node.set_collide_mask(mask)
        for child in node.find_all_matches("**/+GeomNode"):
            child.set_tag("pick_name", name)
            child.set_tag("pick_kind", object_kind)
            child.set_collide_mask(mask)

    def _setup_picking(self) -> None:
        assert self._base is not None and self._base.cam is not None
        from panda3d.core import (
            BitMask32,
            CollisionHandlerQueue,
            CollisionNode,
            CollisionRay,
            CollisionTraverser,
        )

        ray = CollisionRay()
        node = CollisionNode("mouse_picker")
        node.set_from_collide_mask(BitMask32.bit(self._pickable_mask_bit))
        node.set_into_collide_mask(BitMask32.all_off())
        node.add_solid(ray)
        picker_np = self._base.cam.attach_new_node(node)
        queue = CollisionHandlerQueue()
        traverser = CollisionTraverser()
        traverser.add_collider(picker_np, queue)

        self._picker_ray = ray
        self._picker_node = picker_np
        self._picker_queue = queue
        self._picker_traverser = traverser

    def _apply_camera_pose(self) -> None:
        if self._base is None or self._base.cam is None:
            return
        focus_x, focus_y, focus_z = self._orbit_target
        heading_rad = math.radians(self._orbit_heading_deg)
        pitch_rad = math.radians(self._orbit_pitch_deg)
        horizontal = self._orbit_distance * math.cos(pitch_rad)
        x = focus_x + (horizontal * math.sin(heading_rad))
        y = focus_y - (horizontal * math.cos(heading_rad))
        z = focus_z + (self._orbit_distance * math.sin(pitch_rad))
        self._base.cam.set_pos(x, y, z)
        self._base.cam.look_at(focus_x, focus_y, focus_z)

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
            self._pick_from_pointer(pointer_x, pointer_y)
        self._last_right_down = right_down

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
            3.0, min(40.0, self._orbit_distance + (-float(wheel_delta) * 0.01))
        )
        self._apply_camera_pose()

    def _pick_from_pointer(self, pointer_x: int, pointer_y: int) -> None:
        result = self.pick(pointer_x, pointer_y)
        if result is None:
            self._status_queue.append(_QueuedStatus("Pick: no hit"))
            return
        self._pick_queue.append(result)
        self._status_queue.append(_QueuedStatus(f"Pick: {result.object_name}"))

    def pick(self, pointer_x: int, pointer_y: int) -> RawPickResult | None:
        if (
            self._base is None
            or self._base.cam is None
            or self._base.win is None
            or self._picker_ray is None
            or self._picker_queue is None
            or self._picker_traverser is None
            or self._lens is None
        ):
            return None

        width = float(max(1, self._base.win.get_x_size()))
        height = float(max(1, self._base.win.get_y_size()))
        mouse_x = ((float(pointer_x) / width) * 2.0) - 1.0
        mouse_y = 1.0 - ((float(pointer_y) / height) * 2.0)
        cam_node = self._base.cam.node()
        self._picker_ray.set_from_lens(cam_node, mouse_x, mouse_y)
        self._picker_queue.clear_entries()
        self._picker_traverser.traverse(self._base.render)
        if self._picker_queue.get_num_entries() == 0:
            return None
        self._picker_queue.sort_entries()
        entry = self._picker_queue.get_entry(0)
        hit_np = entry.get_into_node_path()
        pick_name = str(hit_np.get_tag("pick_name") or hit_np.get_name() or "").strip()
        if not pick_name:
            return None
        kind = str(hit_np.get_tag("pick_kind") or "node").strip()
        hit_point = entry.get_surface_point(self._base.render)
        return RawPickResult(
            object_name=pick_name,
            machine_id="demo",
            object_id=pick_name,
            object_kind=kind,
            hit_point_world=(float(hit_point.x), float(hit_point.y), float(hit_point.z)),
        )

    def _on_wheel_up(self) -> None:
        self.zoom(120.0)

    def _on_wheel_down(self) -> None:
        self.zoom(-120.0)
