from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    # tools/make_patch.py -> repo root
    return Path(__file__).resolve().parents[1]


def _run(cmd: list[str], *, cwd: Path) -> int:
    print("+", " ".join(cmd))
    return subprocess.call(cmd, cwd=str(cwd))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Create a git-apply compatible patch from the current repo state."
    )
    p.add_argument(
        "-o",
        "--output",
        default="change.patch",
        help="Output patch file path (default: change.patch)",
    )
    p.add_argument(
        "--cached",
        action="store_true",
        help="Create patch from the index (staged changes) instead of working tree.",
    )
    p.add_argument(
        "--check-whitespace",
        action="store_true",
        help="Fail if git reports whitespace errors in the diff.",
    )

    args = p.parse_args(argv)

    root = _repo_root()
    out_path = Path(args.output)
    if not out_path.is_absolute():
        out_path = (root / out_path).resolve()

    diff_cmd = ["git", "diff", "--no-color", "--binary"]
    if args.cached:
        diff_cmd.append("--cached")

    if args.check_whitespace:
        # This checks the working tree/index; it doesn't validate the patch file itself.
        rc = _run(["git", "diff", "--check"] + (["--cached"] if args.cached else []), cwd=root)
        if rc != 0:
            return rc

    print(f"Writing patch to: {out_path}")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    proc = subprocess.run(
        diff_cmd,
        cwd=str(root),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=False,
    )

    if proc.returncode not in (0, 1):
        # git diff returns 1 when differences exist; 0 when none.
        sys.stderr.buffer.write(proc.stdout)
        return proc.returncode

    out_path.write_bytes(proc.stdout)

    if proc.returncode == 0:
        print("(no changes; patch is empty)")
    else:
        print("(ok)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
