from __future__ import annotations

"""Deprecated module.

Historically we used a simple deque-based :class:`InMemBus` to shuttle intents and
telemetry between a client and the core engine in a single process.

As of v0.1 we standardize on :class:`steuerung3d.protocol.transport.InMemTransport`,
which is thread-safe (uses :class:`queue.Queue`) and matches the transport seam we
need for future UDP/ZMQ/WebSocket transports.

This module is kept *only* for backwards compatibility. New code should import:

    from steuerung3d.protocol.transport import InMemTransport

and use that instance wherever an in-memory transport is required.
"""

from warnings import warn

from steuerung3d.protocol.transport import InMemTransport as InMemBus

warn(
    "steuerung3d.core.inmem_bus.InMemBus is deprecated; use "
    "steuerung3d.protocol.transport.InMemTransport instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["InMemBus"]
