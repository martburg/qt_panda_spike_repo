from __future__ import annotations

import sys
from pathlib import Path


def test_no_archive_or_legacy_imports() -> None:
    """Ensure accidental imports from repo-side 'archive/' or 'legacy/' don't creep in.

    Those directories are for reference only and must not become runtime
    dependencies.
    """

    import steuerung3d  # noqa: F401

    bad_paths: list[str] = []
    for name, mod in list(sys.modules.items()):
        if not mod:
            continue
        file = getattr(mod, "__file__", None)
        if not isinstance(file, str):
            continue
        p = Path(file)
        parts = {part.lower() for part in p.parts}
        if "archive" in parts or ("legacy" in parts and "docs" not in parts):
            # docs/legacy is fine (not imported as python); repo-root legacy is not.
            bad_paths.append(f"{name}: {file}")

    assert not bad_paths, "Unexpected imports from archive/ or legacy/:\n" + "\n".join(sorted(bad_paths))
