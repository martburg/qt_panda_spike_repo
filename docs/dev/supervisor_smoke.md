# Supervisor smoke path (proper core fanout)

This is the recommended local smoke path for the current supervisor snapshot.

## Command

```bash
python -m steuerung3d sup --profile configs/supervisor/smoke_2pairs.toml
```

## What it launches

The supervisor launches a **core+densi stack** via:

- `configs/stacks/supervisor_2axes_core_fanout.toml`

That stack starts:

- `core_udp_service`
- two headless DenSis (`Anton`, `Debby`)

It does **not** pre-launch HiPs.

HiPs are opened **on demand** from the supervisor row buttons.

## Telemetry topology

Core runs with UI telemetry fanout:

- `51002` → supervisor
- `51003` → Anton HiP
- `51004` → Debby HiP

This means the opened HiPs receive telemetry from core in the same fanout style as the existing stack profiles.

## HiP hook

Each row has an **Open HiP** button.

- Anton opens with `--telem-in 127.0.0.1:51003`
- Debby opens with `--telem-in 127.0.0.1:51004`

While any HiP launched from the supervisor is still open, synchronized supervisor motion is blocked.

## Expected checks

1. Start the supervisor.
2. Two stable rows appear: `Anton`, `Debby`.
3. `livetick` increases.
4. Press **Open HiP** on one row.
5. The corresponding HiP window opens.
6. Supervisor indicates a HiP-open condition and blocks synchronized motion.
7. Close the HiP and verify the block is removed.

## Notes

- This is the proper **core fanout** setup for the current snapshot.
- It keeps the supervisor axis-centric.
- HiP is treated as an optional single-axis detail tool, not as a mandatory half of the supervised entity.
