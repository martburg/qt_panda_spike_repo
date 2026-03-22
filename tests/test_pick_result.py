from qt_panda_spike.scene.picking import PickResult, RayTraceDebug, Vec3Data


def _trace(*, scene_name: str | None, scene_point: Vec3Data | None, dome_point: Vec3Data | None) -> RayTraceDebug:
    return RayTraceDebug(
        image_x=400.0,
        image_y=300.0,
        normalized_x=0.0,
        normalized_y=0.0,
        ray_origin_world=Vec3Data(0.0, 0.0, 0.0),
        ray_direction_world=Vec3Data(0.0, 1.0, 0.0),
        scene_hit_node_name=scene_name,
        scene_hit_world=scene_point,
        dome_hit_world=dome_point,
    )


def test_pick_result_status_includes_scene_and_dome() -> None:
    result = PickResult(
        camera_position=Vec3Data(1.0, 2.0, 3.0),
        camera_hpr=Vec3Data(10.0, 20.0, 0.0),
        camera_forward=Vec3Data(0.0, 1.0, 0.0),
        view_center=_trace(
            scene_name=None,
            scene_point=None,
            dome_point=Vec3Data(1.0, 32.0, 3.0),
        ),
        pick_trace=_trace(
            scene_name="panel_green",
            scene_point=Vec3Data(0.5, 2.8, 1.0),
            dome_point=Vec3Data(3.0, 25.0, 4.0),
        ),
    )

    assert result.format_status() == (
        "Pick: scene=panel_green @ (0.500, 2.800, 1.000) | dome @ (3.000, 25.000, 4.000)"
    )


def test_pick_result_status_omits_dome_when_not_present() -> None:
    result = PickResult(
        camera_position=Vec3Data(1.0, 2.0, 3.0),
        camera_hpr=Vec3Data(10.0, 20.0, 0.0),
        camera_forward=Vec3Data(0.0, 1.0, 0.0),
        view_center=_trace(scene_name=None, scene_point=None, dome_point=None),
        pick_trace=_trace(
            scene_name="panel_green",
            scene_point=Vec3Data(0.5, 2.8, 1.0),
            dome_point=None,
        ),
    )

    assert result.format_status() == "Pick: scene=panel_green @ (0.500, 2.800, 1.000)"


def test_pick_result_record_contains_split_hits() -> None:
    result = PickResult(
        camera_position=Vec3Data(1.0, 2.0, 3.0),
        camera_hpr=Vec3Data(10.0, 20.0, 0.0),
        camera_forward=Vec3Data(0.0, 1.0, 0.0),
        view_center=_trace(
            scene_name=None,
            scene_point=None,
            dome_point=Vec3Data(1.0, 32.0, 3.0),
        ),
        pick_trace=_trace(
            scene_name="ground",
            scene_point=Vec3Data(2.0, 0.0, 0.0),
            dome_point=Vec3Data(2.0, 30.0, 0.0),
        ),
    )

    record = result.to_record()

    assert record["pick"]["scene_hit_node_name"] == "ground"
    assert record["pick"]["scene_hit_world"]["x"] == 2.0
    assert record["pick"]["dome_hit_world"]["y"] == 30.0
