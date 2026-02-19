"""DenSi compact limit fields VM (txtLimit*).

These are display-only fields on DenSi that mirror HardMin/UserMin/UserMax/HardMax.
Semantics to preserve:
- Format: two decimals + ' m'
- Decimal separator: comma
- Only update fields present in the provided values mapping.
"""

from __future__ import annotations

from dataclasses import dataclass

from ...qtutil.ui_format import fmt_float_de


def _fmt_m(v: float) -> str:
    """Format a length in meters for the compact limit fields."""
    return fmt_float_de(v, ndigits=2, unit="m", empty="")


@dataclass(frozen=True)
class DenSiLimitsVM:
    # object_name -> text
    texts: dict[str, str]


def compute_densi_limits_vm(*, values: dict[str, float], limit_widgets: dict[str, str]) -> DenSiLimitsVM:
    texts: dict[str, str] = {}
    for key, obj_name in dict(limit_widgets).items():
        if key not in values:
            continue
        texts[str(obj_name)] = _fmt_m(float(values[key]))
    return DenSiLimitsVM(texts=texts)
