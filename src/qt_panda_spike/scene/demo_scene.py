from __future__ import annotations

from typing import Any

from .picking import PICK_MASK_BIT


DOME_RADIUS = 30.0


def _make_pickable(np: Any, name: str) -> Any:
    from panda3d.core import BitMask32

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

    cm = CardMaker("ground")
    cm.set_frame(-6, 6, -6, 6)
    ground = render.attach_new_node(cm.generate())
    ground.set_p(-90)
    ground.set_z(-0.01)
    ground.set_color(Vec4(0.15, 0.15, 0.18, 1.0))
    _make_pickable(ground, "ground")

    def add_panel(name: str, x: float, y: float, z: float, color: tuple[float, float, float, float]) -> None:
        card = CardMaker(name)
        card.set_frame(-1.2, 1.2, -0.8, 0.8)
        np = render.attach_new_node(card.generate())
        np.set_pos(x, y, z)
        np.set_hpr(0.0, 0.0, 0.0)
        np.set_color(Vec4(*color))
        _make_pickable(np, name)

    add_panel("panel_red", -3.0, 2.5, 1.2, (0.9, 0.2, 0.2, 1.0))
    add_panel("panel_green", 0.0, 2.8, 1.0, (0.2, 0.85, 0.2, 1.0))
    add_panel("panel_blue", 3.0, 2.5, 1.2, (0.2, 0.4, 0.95, 1.0))
    add_panel("panel_amber", 0.0, -1.2, 1.8, (0.95, 0.65, 0.15, 1.0))

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
