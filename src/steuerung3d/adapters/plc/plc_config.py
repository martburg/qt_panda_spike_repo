from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class PlcWireSpec:
    """
    PLC wire format *configuration*.

    NOTE: The PLC's actual field order is fixed and order-sensitive.
    This spec exists so we can map that fixed order in one place.

    axis_ids:
      - canonical axis order for per-axis fields (enable/vel, pos/vel/en/fault)
    """
    axis_ids: List[str]

    delimiter: str = ";"
    encoding: str = "ascii"

    # Formatting tokens
    float_fmt: str = "{:.6f}"
    true_token: str = "True"
    false_token: str = "False"
