from __future__ import annotations

from typing import List, Optional, Tuple

from steuerung3d.core.net import normalize_host, parse_hostport


def expand_targets(
    explicit_targets: List[str],
    *,
    base: Optional[str],
    count: int,
    base_host: str,
    default_target: Optional[Tuple[str, int]],
) -> List[Tuple[str, int]]:
    """Expand CLI host/port options into a concrete target list."""

    targets: List[Tuple[str, int]] = []
    for s in explicit_targets:
        targets.append(parse_hostport(s))
    if base is not None and int(count) > 0:
        base_port = int(str(base).strip())
        host = normalize_host(base_host)
        for i in range(int(count)):
            targets.append((host, base_port + i))
    if not targets and default_target is not None:
        targets = [default_target]
    return targets


def expand_dev_cmd_targets(base: str, count: int, host: str) -> List[Tuple[str, int]]:
    base_port = int(str(base).strip())
    out: List[Tuple[str, int]] = []
    cmd_host = normalize_host(host)
    for i in range(int(count)):
        out.append((cmd_host, base_port + i))
    return out
