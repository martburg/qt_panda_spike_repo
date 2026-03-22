from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ImagePoint:
    x: float
    y: float


def map_widget_to_image(
    *,
    widget_x: float,
    widget_y: float,
    display_x: float,
    display_y: float,
    display_width: float,
    display_height: float,
    image_width: float,
    image_height: float,
) -> ImagePoint | None:
    if display_width <= 0.0 or display_height <= 0.0:
        return None
    if image_width <= 0.0 or image_height <= 0.0:
        return None
    if widget_x < display_x or widget_y < display_y:
        return None
    if widget_x > display_x + display_width or widget_y > display_y + display_height:
        return None

    u = (widget_x - display_x) / display_width
    v = (widget_y - display_y) / display_height
    return ImagePoint(x=u * image_width, y=v * image_height)
