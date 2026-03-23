# pyright: reportMissingImports=false, reportMissingTypeStubs=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownParameterType=false, reportAttributeAccessIssue=false, reportCallIssue=false
from __future__ import annotations

from typing import Any

DOME_RADIUS = 30.0

PICKABLE_NODE_NAMES = (
    "ground",
    "center_node",
    "left_node",
    "right_node",
    "rear_node",
    "tower_node",
)


def _make_pickable(np: Any, name: str) -> Any:
    from panda3d.core import BitMask32

    from .picking import PICK_MASK_BIT

    np.set_name(name)
    np.set_tag("pick_name", name)
    np.set_tag("pick_owner", name)
    np.set_collide_mask(BitMask32.bit(PICK_MASK_BIT))
    for child in np.find_all_matches("**/+GeomNode"):
        child.set_tag("pick_name", name)
        child.set_tag("pick_owner", name)
        child.set_collide_mask(BitMask32.bit(PICK_MASK_BIT))
    return np


def build_demo_scene(base: Any, *, show_dome: bool = False) -> Any | None:
    from panda3d.core import CardMaker, LineSegs, NodePath, TransparencyAttrib, Vec4

    render = base.render

    axes = LineSegs("axes")
    axes.set_thickness(2.0)

    axes.set_color(1.0, 0.2, 0.2, 1.0)
    axes.move_to(0, 0, 0)
    axes.draw_to(3, 0, 0)

    axes.set_color(0.2, 1.0, 0.2, 1.0)
    axes.move_to(0, 0, 0)
    axes.draw_to(0, 3, 0)

    axes.set_color(0.2, 0.4, 1.0, 1.0)
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

    cm = CardMaker("ground")
    cm.set_frame(-6, 6, -6, 6)
    ground = render.attach_new_node(cm.generate())
    ground.set_p(-90)
    ground.set_z(-0.01)
    ground.set_color(Vec4(0.15, 0.15, 0.18, 1.0))
    _make_pickable(ground, "ground")

    sphere_model = base.loader.load_model("models/misc/sphere")

    def add_node(
        name: str,
        *,
        pos: tuple[float, float, float],
        scale: tuple[float, float, float] | float,
        color: tuple[float, float, float, float],
    ) -> None:
        np = sphere_model.copy_to(render)
        np.set_pos(*pos)
        if isinstance(scale, tuple):
            np.set_scale(*scale)
        else:
            np.set_scale(scale)
        np.set_color(*color)
        _make_pickable(np, name)

    add_node("center_node", pos=(0.0, 0.0, 0.8), scale=0.45, color=(0.95, 0.8, 0.15, 1.0))
    add_node("left_node", pos=(-2.6, 2.1, 1.0), scale=0.55, color=(0.9, 0.2, 0.2, 1.0))
    add_node("right_node", pos=(2.8, 2.4, 1.15), scale=0.6, color=(0.2, 0.45, 0.95, 1.0))
    add_node("rear_node", pos=(0.5, -2.8, 1.5), scale=0.5, color=(0.2, 0.9, 0.35, 1.0))
    add_node(
        "tower_node", pos=(-0.5, 3.8, 1.7), scale=(0.35, 0.35, 1.6), color=(0.9, 0.55, 0.2, 1.0)
    )

    if not show_dome:
        return None

    dome = base.loader.load_model("models/misc/sphere")
    dome.reparent_to(base.cam)
    dome.set_name("dome")
    dome.set_pos(0.0, 0.0, 0.0)
    dome.set_scale(DOME_RADIUS)
    dome.set_two_sided(True)
    dome.set_render_mode_wireframe()
    dome.set_transparency(TransparencyAttrib.M_alpha)
    dome.set_color(0.8, 0.85, 0.95, 0.18)
    return dome
