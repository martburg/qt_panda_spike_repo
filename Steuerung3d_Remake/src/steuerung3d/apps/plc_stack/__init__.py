"""PLC stack app package.

This package exposes importable builders so both:
- the real app entrypoint (__main__) and
- unit tests (SIM / fakes)

use the same wiring.
"""

from .builder import (  # noqa: F401
    PlcStackRuntime,
    build_core,
    build_plc_device,
    collect_axes,
)
