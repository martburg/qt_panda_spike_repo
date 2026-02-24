"""Small networking helpers shared across apps.

We keep these dependency-free and conservative because they are used by CLI entrypoints.

Why this exists:
- Many apps accept `host:port` CLI parameters.
- Historically, several apps implemented their own parsing.

This module centralizes that parsing so behavior stays consistent across the repo.
"""

from __future__ import annotations

from typing import Tuple


def normalize_host(host: str, *, default_host: str = "127.0.0.1") -> str:
    return (host or "").strip() or default_host


def parse_hostport(s: str, *, default_host: str = "127.0.0.1") -> Tuple[str, int]:
    """Parse either `host:port` or bare `port`.

    Behavior matches historical CLI helpers:
    - Empty / whitespace-only is an error.
    - If no colon is present, treat the string as a port and use `default_host`.
    - If `host:` is present with an empty host part, also use `default_host`.
    """

    s = (s or "").strip()
    if not s:
        raise ValueError("empty host:port")

    if s.count(":") == 0:
        return (default_host, int(s))

    host, port_s = s.rsplit(":", 1)
    host = normalize_host(host, default_host=default_host)
    return (host, int(port_s.strip()))
