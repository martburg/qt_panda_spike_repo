# qt_panda_spike

A small standalone spike repo to compare two Panda3D + Qt integration strategies on Windows:

- `native` — Qt hosts Panda as a native child window
- `offscreen` — Panda renders offscreen and Qt displays the latest frame

This repository is intentionally minimal and application-agnostic. It exists to answer a practical question:

> Which Panda3D + Qt integration path is stable enough for interactive viewport work?

## Goals

The spike is successful when one backend can:

- open and remain alive
- orbit the camera with left-drag
- zoom with mouse wheel
- right-click to pick scene geometry
- survive window resizes
- keep input responsive
- render a simple scene consistently for several minutes

## Quick start

Create a virtual environment and install dependencies:

```bash
python -m venv .venv
. .venv/Scripts/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

Run native embedding:

```bash
python -m qt_panda_spike --backend native
```

Run offscreen mode:

```bash
python -m qt_panda_spike --backend offscreen
```

Enable the debug dome:

```bash
python -m qt_panda_spike --backend offscreen --show-dome
```

Enable pick diagnostics, JSONL logging, and debug hit markers:

```bash
python -m qt_panda_spike --backend offscreen --pick-debug
```

Write diagnostics to a specific file:

```bash
python -m qt_panda_spike --backend offscreen --pick-debug --pick-log logs/pick_diagnostics.jsonl
```

## Controls

- Left mouse drag: orbit camera
- Mouse wheel: zoom
- Right mouse click: cast a pick ray
- Resize the main window and observe stability

## Debug flags

By default, the spike now runs clean:

- no debug dome
- no diagnostic JSONL log
- no pick markers

Optional flags:

- `--show-dome` enables the camera-centered debug dome and adds the dome hit to the pick status
- `--pick-debug` enables per-click JSONL diagnostics and the scene/dome hit markers

This keeps the normal pick path uncluttered while still preserving the correlation tools when needed.

## Pick diagnostics

When `--pick-debug` is enabled, each right-click appends one JSON record to `pick_diagnostics.jsonl` by default.

The record includes:

- raw Qt widget click coordinates
- the displayed image rectangle inside the widget
- the mapped Panda image coordinates
- normalized device coordinates for the ray
- camera position, HPR, and forward vector
- center-of-view ray origin/direction plus its scene hit
- clicked ray origin/direction plus its scene hit
- dome hit too, if `--show-dome` is also enabled

## Integration notes

See:

- `docs/integration_findings.md` for the current comparison of native vs offscreen integration
- `docs/overlay_experiments.md` for the overlay behavior findings, including the floating frameless overlay approach

## Notes

- The native backend is the most direct Panda integration path but may run into focus and overlay composition issues.
- The offscreen backend avoids native child-window focus issues by letting Qt own the visible widget.
- The picker uses the real render camera (`base.cam`) consistently, which fixed the earlier mismatch between rendered view and pick ray.
- `--show-dome` and `--pick-debug` are intentionally separate so you can use either or both.
- This repo avoids application-specific control logic on purpose.

## Offscreen buffer sizing

- The offscreen backend now targets a Panda buffer size that follows the Qt viewport size.
- On HiDPI displays it multiplies the widget size by `devicePixelRatioF()`.
- Offscreen resize is now **debounced** rather than applied continuously while you drag the window edge.
- During a live resize drag, Qt keeps showing the last valid frame; once the resize settles briefly, the offscreen buffer is updated to the newest requested size.
- This keeps the offscreen path usable on Panda builds where true live `GraphicsBuffer` resizing is slow or only available through buffer recreation.

## Native embedded input

- The native backend now polls Panda's embedded window for left-drag orbit, mouse wheel zoom, and right-click picking.
- This avoids relying on Qt wrapper mouse events in regions owned by the embedded Panda child window.
