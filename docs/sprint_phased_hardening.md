# Phased hardening sprint plan

## Stage 0 — Recon + baseline
- Map leases/intents/gating paths and PLC codec/DenSi motion law locations.
- Run baseline `pytest -q`.
- Record baseline failures.

## Stage 1 — Core authority: leases + gating
- Add lease intents (rig + axis), idempotent with `req_id`.
- Enforce exclusivity and denial reasons.
- Gate motion intents and final command outputs; safe intents allowed.
- Telemetry exposes lease holders + denial reason.
- Tests: exclusivity, denial, safe outputs.

## Stage 2 — PLC-fidelity tightening
- Lifetick supervision dual thresholds (deadman vs idle).
- Drive/ramp-mode gate.
- Strict wire framing (base + w, EOD + tail, True/False, trailing ';').
- Guide policy documented (echo-only or minimal dynamics).
- Tests: motion-law gates + framing golden cases.

## Stage 3 — Determinism & staleness consolidation
- Central helper for age/stale checks (tick-based).
- Replace ad-hoc staleness checks in hot paths.
- Document safety fallbacks in docs/safety_fallbacks.md.
- Tests: helper edge cases + stale-safe behavior.

## Stage 4 — Performance & observability hardening
- Fanout guard against slow consumers; avoid tick-loop crashes.
- Logging policy audit (no per-tick INFO spam).
- Add light fanout test + update reviewer checklist.

## Acceptance criteria
- No new seam categories; core remains authoritative.
- DenSi stays a device adapter (Seam E in, Seam D out).
- Deterministic behavior: tick-based staleness only.
- All new behavior covered by tests.
