# Testing

The project uses `pytest`.

## Run all tests

From the repo root:

```powershell
pytest -q
```

## What is covered (v0.x)

- Core engine stepping and state updates
- Transport behavior and logging wrappers
- TwinCAT legacy codec field mapping (including `EOD` handling)
- TwinCAT legacy UDP devices:
  - lifetick is sent every frame
  - Windows-safe socket behavior (`WinError 10054` treated as dropped packet)

## Writing new tests

A good test in this repo is:

- deterministic (no sleeps if possible)
- minimal (one concern per test)
- asserts behavior at boundaries (codec ↔ device ↔ core)

Examples to follow:

- `test_plc_twincat_legacy_codec.py` – pure parsing/encoding
- `test_plc_twincat_legacy_device_udp.py` – UDP behavior with a small in-test server

## Windows notes

- `curses` is not available by default on Windows.
- UDP may raise `WinError 10054` when the remote port is unreachable.
- UDP bind may raise `WinError 10049` when trying to bind to an IP not configured on this host.
  The dev stack can fall back to loopback PLC simulators in that case.

