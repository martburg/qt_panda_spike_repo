from qt_panda_spike.ui.picking_coords import map_widget_to_image


def test_map_widget_to_image_center() -> None:
    point = map_widget_to_image(
        widget_x=250.0,
        widget_y=150.0,
        display_x=50.0,
        display_y=0.0,
        display_width=400.0,
        display_height=300.0,
        image_width=800.0,
        image_height=600.0,
    )
    assert point is not None
    assert point.x == 400.0
    assert point.y == 300.0


def test_map_widget_to_image_outside_returns_none() -> None:
    point = map_widget_to_image(
        widget_x=10.0,
        widget_y=150.0,
        display_x=50.0,
        display_y=0.0,
        display_width=400.0,
        display_height=300.0,
        image_width=800.0,
        image_height=600.0,
    )
    assert point is None
