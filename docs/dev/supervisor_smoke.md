# Supervisor smoke path

Use this when you want a quick manual bring-up of the first supervisor slice.

## Command

```bash
python -m steuerung3d sup --profile configs/supervisor/smoke_2pairs.toml
```

## What it does

- starts the supervisor GUI/runtime
- launches two headless HiP processes (`Anton`, `Debby`)
- launches two headless DenSi runtimes in JSON wire mode
- binds supervisor group actions to per-DenSi UDP action inputs

## Expected first checks

- the window appears with a global status line
- both pairs show up in the table
- `livetick` changes over time
- `selected` checkboxes can be toggled
- `Recover` shows the placeholder message

## Basic interaction checks

1. Press **Reset EStop** and verify no crash / continued livetick updates.
2. Toggle **chkEsTaster** and verify the pairs remain alive.
3. Press **Resync** and verify no crash / continued updates.
4. Toggle one pair's **selected** checkbox and verify the row reflects the change.

## Notes

- This is a smoke path, not a full semantic acceptance test.
- It depends on a local Qt environment.
- The DenSi launches use `--wire-proto json` to stay on the internal snapshot path during early supervisor testing.


Notes:
- The smoke profile intentionally launches only DenSi participants for now. Launching multiple HiP processes against the same single-consumer telemetry UDP bind is not valid with the current transport.
- The telemetry decoder now tolerates non-numeric DenSi params such as SystemTime and enum-name fields.
