from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HiPSmokeParamSpec:
    name: str
    group: str
    test_value: float
    restore_value: float | None = None


SAFE_HIP_SMOKE_PARAMS: tuple[HiPSmokeParamSpec, ...] = (
    HiPSmokeParamSpec(name="VelMax", group="vel", test_value=1.75, restore_value=1.0),
)
