import importlib


def test_core_udp_service_modules_importable() -> None:
    importlib.import_module("steuerung3d.apps.core_udp_service.facts_builder")
    importlib.import_module("steuerung3d.apps.core_udp_service.reporter")
    importlib.import_module("steuerung3d.apps.core_udp_service.runtime_loop")
