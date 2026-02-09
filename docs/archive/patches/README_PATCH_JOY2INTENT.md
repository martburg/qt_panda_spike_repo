# Patch: joy2intent gamepad tests (RawControls buttons)

This drop-in fixes `synthesize_intents()` to work with the `RawControls` object used by the gamepad tests.

## What was wrong
The mapper assumed a field `rc.pressed` (a set of pressed button indices). The tests pass `RawControls` where pressed state is encoded as a `buttons` bitfield list (0/1).

## What changed
- Added a small helper to compute pressed-button indices from either `rc.pressed` **or** `rc.buttons`.
- Added compatible mapping for `prev_active_winch_idxs` (indices) vs `enabled_winch_ids` (ids), so deadman-release disables the correct winches.

## Install
Extract into repo root (preserving paths).

Files:
- `src/steuerung3d/apps/joy2intent/mapping.py`
