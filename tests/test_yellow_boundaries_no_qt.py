from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _iter_py_files(root: Path) -> list[Path]:
    return [p for p in root.rglob("*.py") if p.is_file()]


def _has_qt(text: str) -> bool:
    return any(token in text for token in ("PySide6", "QtCore", "QtWidgets"))


def test_yellow_pure_layers_no_qt() -> None:
    root = _repo_root() / "src" / "steuerung3d" / "apps" / "yellow"
    for folder in ("domain", "engines", "runtimes"):
        for path in _iter_py_files(root / folder):
            content = path.read_text(encoding="utf-8")
            assert not _has_qt(content), f"Qt import in {path}"


def test_yellow_vm_panels_no_qt() -> None:
    root = _repo_root() / "src" / "steuerung3d" / "apps" / "yellow" / "panels"
    for path in _iter_py_files(root):
        if not path.name.endswith("_vm.py"):
            continue
        content = path.read_text(encoding="utf-8")
        assert not _has_qt(content), f"Qt import in {path}"
