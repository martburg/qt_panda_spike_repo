# qt_panda_spike

A small standalone spike repo for Panda3D + Qt integration on Windows.

The spike originally compared two viewport paths:

- `native` — Qt hosts Panda as a native child window
- `offscreen` — Panda renders offscreen and Qt displays the latest frame

The current focus is now explicit:

> Use the **native** path as the main route and keep the scene deliberately simple so we can stabilize resize, orbit, zoom, and picking.

## Goals

The spike is successful when the native backend can:

- open and remain alive
- resize with the Qt window without losing the Panda content
- orbit the camera with left-drag
- zoom with mouse wheel
- right-click to pick simple scene nodes
- keep input responsive for several minutes

## Quick start

Create a virtual environment and install dependencies:

```bash
python -m venv .venv
. .venv/Scripts/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

Run the native path:

```bash
python -m qt_panda_spike --backend native
```

The offscreen backend is still present as a comparison path:

```bash
python -m qt_panda_spike --backend offscreen
```

Enable the debug dome:

```bash
python -m qt_panda_spike --backend native --show-dome
```

Enable pick diagnostics and debug hit markers:

```bash
python -m qt_panda_spike --backend native --pick-debug
```

Write diagnostics to a specific file:

```bash
python -m qt_panda_spike --backend native --pick-debug --pick-log logs/pick_diagnostics.jsonl
```

## Controls

- Left mouse drag: orbit camera
- Mouse wheel: zoom
- Right mouse click: cast a pick ray
- Resize the main window and observe whether the Panda child window tracks the Qt viewport area

## Scene

The scene is intentionally generic and not domain-specific yet. It contains:

- ground plane and grid
- axis lines
- a handful of simple pickable nodes with stable names

That keeps the spike focused on viewport behavior rather than scene meaning.

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

- `docs/integration_findings.md` for the current comparison and the native-first decision
- `docs/overlay_experiments.md` for the earlier overlay findings

## Notes

- The native backend is now the preferred route for the spike.
- Offscreen remains available only as a comparison path and fallback.
- The viewport overlay is intentionally out of the active runtime path for now so it does not obscure the native Panda child window while resize/input behavior is being stabilized.
- The picker uses the real render camera (`base.cam`) consistently.
