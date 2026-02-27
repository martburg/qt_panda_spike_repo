# REFOS Plan — Lane 1 Rename: lifrtick → lifetick

## Metadata
- slug: lifrtick-to-lifetick
- created_at: 2026-02-27 11:55
- version: 01
- lane: 1
- stage_intent: Stage 1 structural only (no semantic change)
- repo_branch: (not specified)
- protecting_tests_count_guess: 10+

## Refactor Target
Correct all occurrences of the typo “lifrtick” to “lifetick” (the canonical spelling) in configs, code, filenames, and docs. Do not introduce “livetick”. Do not rename anything already spelled “lifetick”.

## Lane Decision
Lane 1 (structural only): No behavior change, no semantic drift. Only typo correction.

## Stage Roadmap
- Stage 0 findings:
  - “lifrtick” appears in config files, code, logger names, TOML keys, filenames, and docs.
  - “lifetick” is canonical and used in tests, telemetry, PLC, UI, docs.
  - Config keys/files/modules named “lifrtick”: src/steuerung3d/config/lifrtick_config.py, configs/debug/lifrtick.toml, usages in src/steuerung3d/core/executor.py.
  - Protecting tests: all tests referencing “lifetick” (EchoLifeTick, LifetickUItx, lifetick_echo).
- Stage 1 structural steps:
  1. Rename all “lifrtick” → “lifetick” in code, configs, docs, filenames, directories.
  2. Update symbol names, logger names, TOML keys, and references.
  3. Update test references and doc mentions if typo present.
  4. Commit all changes atomically to avoid partial rename states.
  5. Safety check: ensure all “lifrtick” references are gone, “lifetick” definitions exist, and “livetick” is not introduced.
- Stage 2 semantic steps: Not applicable (Lane 1 only).

## Files Expected to Change
- configs/debug/lifrtick.toml → configs/debug/lifetick.toml
- src/steuerung3d/config/lifrtick_config.py → src/steuerung3d/config/lifetick_config.py
- src/steuerung3d/core/executor.py
- Any logger, TOML key, or config reference using “lifrtick”
- Any doc mentioning “lifrtick” (if typo present)

## Protecting Tests
- tests/test_livetick_echo_pipeline.py
- tests/unit/test_livetick_roundtrip.py
- tests/integration/test_roundtrip_core_hip_plc.py
- tests/test_axis_router.py
- tests/unit/test_densi_lifetick_vm.py
- tests/test_plc_twincat_legacy_device_udp.py
- tests/test_plc_twincat_legacy_codec.py
- tests/test_protocol_legacy_plc_uplink.py
- tests/test_axis_fsm.py
- tests/unit/test_densi_plc_anton_motion.py

## Required Gates
- pytest -q
- python -m steuerung3d up --profile 1dev_sim

## Risks / Unknowns
- Partial rename state if not committed atomically.
- Missed references in docs or comments.
- Accidental introduction of “livetick”.

## Questions
None.
