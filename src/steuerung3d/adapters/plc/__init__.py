"""PLC-facing adapters (real PLC or PLC simulator).

In v0.1 this package focuses on a small, schema-driven line codec and a UDP
PLC simulator app.

The real Beckhoff/TwinCAT code sends semicolon-separated fields. The exact
field order varies between installations, so we keep the codec configurable.
"""
