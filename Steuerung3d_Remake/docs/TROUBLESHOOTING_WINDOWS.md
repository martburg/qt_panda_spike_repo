# Windows troubleshooting

## `ModuleNotFoundError: No module named '_curses'`

Windows Python does not ship `curses` by default. The dev stack is implemented as plain stdout for
portability.

If you ever need curses on Windows for a different tool:

```powershell
pip install windows-curses
```

## UDP `WinError 10054`

On Windows, UDP can raise `ConnectionResetError` / `WinError 10054` on `recvfrom()` after the peer
responds with an ICMP “Port Unreachable” (e.g. the remote port is not listening).

In this repo, UDP device adapters treat this like a dropped packet (best-effort receive) so the core
runner does not crash during off-network development.

If you see it while expecting real traffic, verify:

- the remote IP/port is correct
- the PLC program/task is running and listening on the port
- Windows firewall rules allow the configured UDP ports

## UDP `WinError 10049`

`WinError 10049` means “cannot assign requested address”. It typically occurs when you try to bind a
socket to a local IP that is not configured on the host.

Example: binding to `172.16.17.5` while not being on the PLC subnet.

Fixes:

- run on a machine that has the `controller_ip` configured
- or use the dev stack’s loopback UDP SIM fallback (automatic when `controller_ip` is missing)

## Firewall

Allow inbound/outbound UDP for the controller local ports (e.g. `15001..15006`) when talking to real
PLCs.
