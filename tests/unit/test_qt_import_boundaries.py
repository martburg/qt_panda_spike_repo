from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _iter_py_files(root: Path) -> list[Path]:
    return [p for p in root.rglob("*.py") if p.is_file()]


def _has_pyside(text: str) -> bool:
    return "PySide6" in text


def test_no_qt_in_engines_and_runtimes() -> None:
    root = _repo_root() / "src" / "steuerung3d" / "apps" / "yellow"
    for folder in ("engines", "runtimes"):
        for path in _iter_py_files(root / folder):
            content = path.read_text(encoding="utf-8")
            assert not _has_pyside(content), f"PySide6 import in {path}"


def test_qt_imports_are_limited_in_panels() -> None:
    root = _repo_root() / "src" / "steuerung3d" / "apps" / "yellow" / "panels"
    allow = {"densi_estop_checkboxes.py"}
    for path in _iter_py_files(root):
        content = path.read_text(encoding="utf-8")
        if not _has_pyside(content):
            continue
        if path.name in allow:
            continue
        if path.name.endswith("_render.py"):
            continue
        assert False, f"PySide6 import in non-render panel: {path}"
