# Panda3D + Qt integration findings

This repository compares two ways to combine Panda3D rendering with a Qt user interface:

- **Native embedding**: Panda renders into a native child window hosted by Qt.
- **Offscreen rendering**: Panda renders into an offscreen buffer and Qt displays the result in a regular widget.

## Current decision

For this spike, the decision is now:

- **Choose the native backend as the active path**
- keep the scene intentionally simple
- work first on **resize, orbit, zoom, and picking**
- keep the offscreen backend only as a comparison path

## Why native wins here

For an interaction-first viewport spike, native gives the shortest path to the behavior we actually care about:

- direct Panda3D window ownership
- direct camera interaction
- direct scene picking
- fewer presentation layers between Panda and the screen

That makes it the better place to solve the hard problems first:

- native child window resize tracking
- stable orbit behavior
- predictable zoom behavior
- reliable pick rays against visible geometry

## Scope discipline

The scene should stay generic for now.

We do **not** need meaningful domain geometry yet. We only need enough pickable nodes to exercise:

- visible depth and spacing
- camera movement around a recognizable center
- hit reporting against named objects

## Native backend

### Strengths

- Direct Panda3D window ownership
- Good fit for orbit, zoom, and picking
- Good baseline for editor-style interaction work

### Active work items

- Resize behavior of the embedded Panda child window
- Orbit around a stable focus point rather than ad-hoc camera motion
- Zoom as camera-distance control
- Picking against simple named nodes

### Current implementation notes

- Native mode polls Panda input directly for drag, wheel, and right-click behavior
- The camera now orbits a stable target point using heading, pitch, and distance
- Native resize explicitly requests a new Panda window size in addition to updating lens aspect ratio

## Offscreen backend

### Status

Still useful as a comparison path, but no longer the main direction of the spike.

It remains relevant if later work needs richer Qt composition, but it is not where the next stabilization effort should go.

## Overlay note

Earlier experiments showed that a floating frameless Qt overlay can sit above the native Panda child window.

That finding remains useful, but the overlay is currently kept out of the active runtime path so it does not obscure the viewport while native resize/input behavior is being stabilized.

## Recommendation

Continue with the native backend until these are convincingly solid:

- visible resize tracking
- stable orbit
- stable zoom
- stable picking on simple nodes

Only after that should additional composition layers be brought back in.
