# tools/check.py
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str], *, cwd: Path) -> int:
    print("+", " ".join(cmd))
    return subprocess.call(cmd, cwd=str(cwd))


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _maybe_run_pyright(root: Path) -> int:
    # Prefer installed "pyright" executable (node or python wrapper).
    exe = shutil.which("pyright")
    # exe = None
    if exe is None:
        print("! pyright not found on PATH; skipping type check")
        return 0
    return run([exe, "-p", str(root / "pyrightconfig.json")], cwd=root)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Repo health gate (Lane 1 safe)")
    p.add_argument(
        "--no-ruff",
        action="store_true",
        help="Skip ruff lint + format checks.",
    )
    p.add_argument(
        "--no-pyright",
        action="store_true",
        help="Skip pyright type check.",
    )
    p.add_argument(
        "--no-pytest",
        action="store_true",
        help="Skip pytest.",
    )
    p.add_argument(
        "--integration",
        action="store_true",
        help="Also run integration tests (pytest -m integration).",
    )

    args = p.parse_args(argv)

    root = repo_root()

    # 1) ruff lint + formatting
    if not args.no_ruff:
        rc = run([sys.executable, "-m", "ruff", "check", str(root)], cwd=root)
        if rc != 0:
            return rc

        rc = run([sys.executable, "-m", "ruff", "format", "--check", str(root)], cwd=root)
        if rc != 0:
            return rc

    # 2) optional type check
    if not args.no_pyright and (root / "pyrightconfig.json").exists():
        rc = _maybe_run_pyright(root)
        if rc != 0:
            return rc

    # 3) unit tests
    if not args.no_pytest:
        rc = run([sys.executable, "-m", "pytest", "-q"], cwd=root)
        if rc != 0:
            return rc

        if args.integration:
            rc = run([sys.executable, "-m", "pytest", "-q", "-m", "integration"], cwd=root)
            if rc != 0:
                return rc

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
