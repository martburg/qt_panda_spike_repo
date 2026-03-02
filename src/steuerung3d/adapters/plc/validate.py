from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Type

if TYPE_CHECKING:
    from .plc_endpoint import PlcEndpoint


@dataclass(frozen=True)
class PlcValidationError(Exception):
    message: str

    def __str__(self) -> str:
        return self.message


def require_single_axis_id(
    axis_ids: List[str] | None,
    *,
    context: str,
    exc_type: Type[Exception] = ValueError,
) -> str:
    """Return the single required axis_id or raise.

    Canonical PLC telegrams are per-axis endpoint, so we currently require
    exactly one axis_id.

    Args:
        axis_ids: Axis id list (may be None/empty).
        context: Human-readable context for error messages.
        exc_type: Exception type to raise (ValueError by default).

    """
    ids = [str(x) for x in (axis_ids or [])]
    if len(ids) != 1:
        msg = f"{context} must have exactly one axis_id; got axis_ids={ids}"
        # PlcValidationError is a dataclass exception that expects message=...
        if exc_type is PlcValidationError:
            raise PlcValidationError(msg)
        raise exc_type(msg)
    return ids[0]


def validate_endpoints(endpoints: List[PlcEndpoint]) -> None:
    """Validate PLC endpoint configuration.

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
        axis_id = require_single_axis_id(
            e.axis_ids,
            context=f"Endpoint '{e.name}'",
            exc_type=PlcValidationError,
        )

        # axis ownership uniqueness
        if axis_id in owned_by:
            raise PlcValidationError(
                f"Axis '{axis_id}' is owned by both '{owned_by[axis_id]}' and '{e.name}'"
            )
        owned_by[axis_id] = e.name

        # codec/spec should match endpoint assignment
        spec_axes = list(getattr(e.codec, "spec").axis_ids)  # PlcCodec.spec.axis_ids
        if spec_axes != e.axis_ids:
            raise PlcValidationError(
                f"Endpoint '{e.name}': codec.spec.axis_ids={spec_axes} "
                f"must exactly match endpoint.axis_ids={e.axis_ids} (order matters)"
            )
