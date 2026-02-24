from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Set

from .plc_endpoint import PlcEndpoint


@dataclass(frozen=True)
class PlcValidationError(Exception):
    message: str

    def __str__(self) -> str:
        return self.message


def validate_endpoints(endpoints: List[PlcEndpoint]) -> None:
    """
    Validate mixed PLC axis assignment.

    Rules:
      - endpoint names must be unique
      - each endpoint must own exactly one axis_id (canonical PLC telegrams are per axis)
      - an axis_id may be owned by at most one endpoint
      - endpoint axis_ids must match codec.spec.axis_ids (strongly recommended)

    Raises PlcValidationError on violation.
    """
    if not endpoints:
        raise PlcValidationError("No PLC endpoints configured")

    # unique endpoint names
    names = [e.name for e in endpoints]
    if len(set(names)) != len(names):
        raise PlcValidationError(f"Duplicate PLC endpoint names: {names}")

    owned_by: Dict[str, str] = {}
    for e in endpoints:
        if not e.axis_ids:
            raise PlcValidationError(f"Endpoint '{e.name}' has empty axis_ids")
        if len(e.axis_ids) != 1:
            raise PlcValidationError(
                f"Endpoint '{e.name}' must have exactly one axis_id for the canonical PLC codec; "
                f"got axis_ids={e.axis_ids}"
            )

        # axis ownership uniqueness
        for ax in e.axis_ids:
            if ax in owned_by:
                raise PlcValidationError(
                    f"Axis '{ax}' is owned by both '{owned_by[ax]}' and '{e.name}'"
                )
            owned_by[ax] = e.name

        # codec/spec should match endpoint assignment
        spec_axes = list(getattr(e.codec, "spec").axis_ids)  # PlcCodec.spec.axis_ids
        if spec_axes != e.axis_ids:
            raise PlcValidationError(
                f"Endpoint '{e.name}': codec.spec.axis_ids={spec_axes} "
                f"must exactly match endpoint.axis_ids={e.axis_ids} (order matters)"
            )
