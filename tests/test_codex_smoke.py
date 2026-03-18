def test_true_is_true() -> None:
    assert True


def test_import_steuerung3d_package() -> None:
    import importlib

    module = importlib.import_module("steuerung3d")
    assert module.__name__ == "steuerung3d"
