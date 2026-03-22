from __future__ import annotations

from dataclasses import dataclass
from typing import Any


PICK_MASK_BIT = 1


@dataclass(frozen=True)
class Vec3Data:
    x: float
    y: float
    z: float

    def to_record(self) -> dict[str, float]:
        return {"x": self.x, "y": self.y, "z": self.z}


@dataclass(frozen=True)
class RayTraceDebug:
    image_x: float
    image_y: float
    normalized_x: float
    normalized_y: float
    ray_origin_world: Vec3Data
    ray_direction_world: Vec3Data
    scene_hit_node_name: str | None
    scene_hit_world: Vec3Data | None
    dome_hit_world: Vec3Data | None

    def to_record(self) -> dict[str, object]:
        return {
            "image_x": self.image_x,
            "image_y": self.image_y,
            "normalized_x": self.normalized_x,
            "normalized_y": self.normalized_y,
            "ray_origin_world": self.ray_origin_world.to_record(),
            "ray_direction_world": self.ray_direction_world.to_record(),
            "scene_hit_node_name": self.scene_hit_node_name,
            "scene_hit_world": None if self.scene_hit_world is None else self.scene_hit_world.to_record(),
            "dome_hit_world": None if self.dome_hit_world is None else self.dome_hit_world.to_record(),
        }


@dataclass(frozen=True)
class PickResult:
    camera_position: Vec3Data
    camera_hpr: Vec3Data
    camera_forward: Vec3Data
    view_center: RayTraceDebug
    pick_trace: RayTraceDebug

    def format_status(self) -> str:
        fragments: list[str] = []
        if self.pick_trace.scene_hit_world is not None and self.pick_trace.scene_hit_node_name is not None:
            point = self.pick_trace.scene_hit_world
            fragments.append(
                f"scene={self.pick_trace.scene_hit_node_name} @ ({point.x:.3f}, {point.y:.3f}, {point.z:.3f})"
            )
        if self.pick_trace.dome_hit_world is not None:
            point = self.pick_trace.dome_hit_world
            fragments.append(f"dome @ ({point.x:.3f}, {point.y:.3f}, {point.z:.3f})")
        if not fragments:
            return "Pick: no hit"
        return "Pick: " + " | ".join(fragments)

    def to_record(self) -> dict[str, object]:
        return {
            "camera": {
                "position": self.camera_position.to_record(),
                "hpr": self.camera_hpr.to_record(),
                "forward": self.camera_forward.to_record(),
            },
            "view_center": self.view_center.to_record(),
            "pick": self.pick_trace.to_record(),
        }


class Picker:
    def __init__(self, base: Any, *, dome_radius: float = 30.0, include_dome_hit: bool = False) -> None:
        from panda3d.core import BitMask32, CollisionHandlerQueue, CollisionNode, CollisionRay, CollisionTraverser

        self._base = base
        self._pick_cam = base.cam
        self._pick_lens = self._pick_cam.node().get_lens()
        self._dome_radius = float(dome_radius)
        self._include_dome_hit = bool(include_dome_hit)
        self._mask = BitMask32.bit(PICK_MASK_BIT)
        self._traverser = CollisionTraverser("viewport_picker")
        self._queue = CollisionHandlerQueue()

        self._ray = CollisionRay()
        node = CollisionNode("viewport_pick_ray")
        node.set_from_collide_mask(self._mask)
        node.set_into_collide_mask(BitMask32.all_off())
        node.add_solid(self._ray)

        self._picker_np = self._pick_cam.attach_new_node(node)
        self._traverser.add_collider(self._picker_np, self._queue)

    @property
    def mask(self) -> Any:
        return self._mask

    def pick(self, image_x: float, image_y: float, image_width: float, image_height: float) -> PickResult | None:
        if image_width <= 0.0 or image_height <= 0.0:
            return None

        camera_position = self._vec3_from_p3(self._pick_cam.get_pos(self._base.render))
        camera_hpr = self._vec3_from_p3(self._pick_cam.get_hpr(self._base.render))
        camera_forward = self._vec3_from_p3(self._pick_cam.get_quat(self._base.render).get_forward())

        view_center = self._trace(image_width * 0.5, image_height * 0.5, image_width, image_height)
        pick_trace = self._trace(image_x, image_y, image_width, image_height)
        if view_center is None or pick_trace is None:
            return None

        return PickResult(
            camera_position=camera_position,
            camera_hpr=camera_hpr,
            camera_forward=camera_forward,
            view_center=view_center,
            pick_trace=pick_trace,
        )

    def _trace(
        self,
        image_x: float,
        image_y: float,
        image_width: float,
        image_height: float,
    ) -> RayTraceDebug | None:
        if image_width <= 0.0 or image_height <= 0.0:
            return None

        from panda3d.core import Point2, Point3, Vec3

        nx = (float(image_x) / float(image_width)) * 2.0 - 1.0
        ny = 1.0 - (float(image_y) / float(image_height)) * 2.0

        near_point = Point3()
        far_point = Point3()
        if not self._pick_lens.extrude(Point2(nx, ny), near_point, far_point):
            return None

        direction_cam = Vec3(far_point - near_point)
        if direction_cam.length_squared() <= 0.0:
            return None
        direction_cam.normalize()

        self._ray.set_origin(near_point)
        self._ray.set_direction(direction_cam)

        ray_origin_world = self._base.render.get_relative_point(self._pick_cam, near_point)
        ray_direction_world = self._base.render.get_relative_vector(self._pick_cam, direction_cam)
        if ray_direction_world.length_squared() <= 0.0:
            return None
        ray_direction_world.normalize()

        self._queue.clear_entries()
        self._traverser.traverse(self._base.render)

        scene_hit_node_name: str | None = None
        scene_hit_world: Vec3Data | None = None
        if self._queue.get_num_entries() > 0:
            self._queue.sort_entries()
            entry = self._queue.get_entry(0)
            point = entry.get_surface_point(self._base.render)
            into_np = entry.get_into_node_path()
            scene_hit_node_name = self._resolve_pick_name(into_np)
            scene_hit_world = self._vec3_from_p3(point)

        dome_hit_world = self._compute_dome_hit(ray_direction_world) if self._include_dome_hit else None

        return RayTraceDebug(
            image_x=float(image_x),
            image_y=float(image_y),
            normalized_x=float(nx),
            normalized_y=float(ny),
            ray_origin_world=self._vec3_from_p3(ray_origin_world),
            ray_direction_world=self._vec3_from_p3(ray_direction_world),
            scene_hit_node_name=scene_hit_node_name,
            scene_hit_world=scene_hit_world,
            dome_hit_world=dome_hit_world,
        )

    def _compute_dome_hit(self, ray_direction_world: Any) -> Vec3Data | None:
        from panda3d.core import Vec3

        camera_position = self._pick_cam.get_pos(self._base.render)
        direction = Vec3(ray_direction_world)
        if direction.length_squared() <= 0.0:
            return None
        direction.normalize()
        dome_hit = camera_position + (direction * self._dome_radius)
        return self._vec3_from_p3(dome_hit)

    @staticmethod
    def _resolve_pick_name(into_np: Any) -> str | None:
        owner_name = into_np.get_net_tag("pick_owner")
        if owner_name:
            return str(owner_name)
        direct_name = into_np.get_net_tag("pick_name")
        if direct_name:
            return str(direct_name)
        fallback = into_np.get_name()
        return str(fallback) if fallback else None

    @staticmethod
    def _vec3_from_p3(value: Any) -> Vec3Data:
        return Vec3Data(float(value.x), float(value.y), float(value.z))
