# Safety Fallbacks

Deterministic fallback behavior by seam (A-F):

- Seam D stale => Seam E commands go safe (disable and/or vel=0).
- Seam F stale in SYNCED => v_safe_world = 0 (reserved for future implementation).
- Seam C stale is UI-only; no safety effect.

Notes:
- All staleness checks are tick-based (no wall-clock dependence).
- Safety fallbacks must be idempotent and deterministic.
