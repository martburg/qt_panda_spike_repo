"""
Legacy PLC semicolon-line codec (Anton).

Implements the exact field order used by the Beckhoff ST program
`KommAnton__MAIN.st`.

See: docs/protocols/legacy_plc_anton.md
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Sequence, Tuple


def _split_fields(line: str, sep: str) -> List[str]:
    """Split a PLC line into fields.

    TwinCAT CSV-style packets often end with a trailing separator (e.g. ';').
    We strip empty tail fields so the parser is stable.
    """

    raw = [p.strip() for p in line.strip().split(sep)]
    while raw and raw[-1] == "":
        raw.pop()
    return raw


def _format_fields(values: Sequence[object], sep: str, trailing_sep: bool) -> str:
    s = sep.join(str(v) for v in values)
    if trailing_sep:
        s += sep
    return s


@dataclass(frozen=True)
class PlcLineSchema:
    """Defines the *positional* fields of a PLC UDP line.

    This is intentionally simple:
      - no quoting
      - no escaping
      - values are positional

    Example (core -> PLC):
        fields=["tick", "axis", "enable", "vel"]
        line:   123;X;1;0.5;
    """

    fields: Tuple[str, ...]
    sep: str = ";"
    trailing_sep: bool = True


@dataclass
class PlcLineCodec:
    """Schema-driven encoder/decoder for semicolon-separated PLC lines."""

    rx: PlcLineSchema = PlcLineSchema(("tick", "axis", "enable", "vel"))
    tx: PlcLineSchema = PlcLineSchema(("tick", "axis", "enabled", "vel", "pos", "fault"))

    def decode(self, line: str, *, schema: PlcLineSchema) -> Dict[str, str]:
        parts = _split_fields(line, schema.sep)
        out: Dict[str, str] = {}
        for i, name in enumerate(schema.fields):
            if i >= len(parts):
                break
            out[name] = parts[i]
        # keep extras (for forward compatibility)
        if len(parts) > len(schema.fields):
            out["_extra"] = schema.sep.join(parts[len(schema.fields) :])
        return out

    def encode(self, values: Mapping[str, object], *, schema: PlcLineSchema) -> str:
        ordered: List[object] = []
        for name in schema.fields:
            if name not in values:
                raise KeyError(f"Missing required field '{name}'")
            ordered.append(values[name])
        return _format_fields(ordered, schema.sep, schema.trailing_sep)

    # ---- convenience helpers (typed access) ----
    def decode_rx(self, line: str) -> Dict[str, str]:
        return self.decode(line, schema=self.rx)

    def decode_tx(self, line: str) -> Dict[str, str]:
        return self.decode(line, schema=self.tx)

    def encode_rx(self, values: Mapping[str, object]) -> str:
        return self.encode(values, schema=self.rx)

    def encode_tx(self, values: Mapping[str, object]) -> str:
        return self.encode(values, schema=self.tx)


def parse_int(v: str, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def parse_float(v: str, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def parse_bool(v: str, default: bool = False) -> bool:
    if v is None:
        return default
    s = str(v).strip().lower()
    if s in ("1", "true", "t", "yes", "y", "on"):
        return True
    if s in ("0", "false", "f", "no", "n", "off"):
        return False
    return default


def coerce(mapping: Mapping[str, str], *, key: str, typ: str) -> Optional[object]:
    if key not in mapping:
        return None
    raw = mapping[key]
    if typ == "int":
        return parse_int(raw)
    if typ == "float":
        return parse_float(raw)
    if typ == "bool":
        return parse_bool(raw)
    return raw
