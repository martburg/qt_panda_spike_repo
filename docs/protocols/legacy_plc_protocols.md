# Legacy PLC UDP Protocols (Index)

This section documents the legacy Beckhoff UDP protocol used between the controller (`172.16.17.5`)
and the individual axis PLCs (`172.16.17.x`).

All payloads are ASCII `;`-delimited and order-sensitive.

## PLC protocol pages

| Axis / PLC | PLC IP | PLC bind | Controller bind | Doc |
|---|---:|---|---|---|
| Anton | 172.16.17.2 | 172.16.17.2:15001 | 172.16.17.5:15002 | `legacy_plc_anton.md` |
| Debby | 172.16.17.3 | 172.16.17.3:15001 | 172.16.17.5:15002 | `legacy_plc_debby.md` (TODO) |
| Burt  | 172.16.17.4 | 172.16.17.4:15001 | 172.16.17.5:15002 | `legacy_plc_burt.md` (TODO) |
| Cecil | 172.16.17.1 | 172.16.17.1:15001 | 172.16.17.5:15002 | `legacy_plc_cecil.md` (TODO) |

## Contract guarantees (shared)

- Delimiter `;`, usually a trailing `;` is present.
- Decimal separator is `.`
- `Intent` is `"True"` / `"False"` (string), not a boolean.
- Parsing is positional: do not reorder fields.
