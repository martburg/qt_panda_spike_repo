from __future__ import annotations

"""Deprecated module.

`InMemBus` used to live here (deque-based). The project now standardizes on the
thread-safe `InMemTransport` implementation in `steuerung3d.protocol.transport`.

This shim preserves the old import path:

    from steuerung3d.protocol.inmem_bus import InMemBus

but returns the new implementation.

Prefer:

    from steuerung3d.protocol.transport import InMemTransport
"""

from warnings import warn

from steuerung3d.protocol.transport import InMemTransport as InMemBus

warn(
    "steuerung3d.protocol.inmem_bus.InMemBus is deprecated; use "
    "steuerung3d.protocol.transport.InMemTransport instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["InMemBus"]
