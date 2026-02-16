
def test_densi_engine_imports() -> None:
    # Smoke test: ensure engines package exports DenSiEngine and enums.
    from steuerung3d.apps.yellow.engines import DenSiEngine, DenSiTickResult, EStopState, L0Top, L0Sub

    assert DenSiEngine is not None
    assert DenSiTickResult is not None
    assert EStopState.ESTOP.name == "ESTOP"
    assert L0Top.START.name == "START"
    assert L0Sub.IDLE.name == "IDLE"
