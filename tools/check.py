# tools/check.py
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def run(cmd: list[str]) -> int:
    print("+", " ".join(cmd))
    return subprocess.call(cmd)


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]

    # ruff
    rc = run([sys.executable, "-m", "ruff", "check", str(repo_root)])
    if rc != 0:
        return rc

    # optional: enforce formatting without changing files
    rc = run([sys.executable, "-m", "ruff", "format", "--check", str(repo_root)])
    return rc


if __name__ == "__main__":
    raise SystemExit(main())