# Legacy PLC UDP Protocol (Common)

This page documents the **shared** Beckhoff PLC UDP protocol shape used by the legacy controller.

All payloads are ASCII, `;`-delimited, and **order-sensitive**.

## Contract guarantees

- Delimiter `;`, usually a trailing `;` is present.
- Decimal separator is `.`
- `Intent` is the string `"True"` / `"False"` (not a boolean).
- Parsing is positional: **do not reorder fields**.

## Axis-specific pages

The per-axis pages only differ by **addresses / endpoint tuples**.
