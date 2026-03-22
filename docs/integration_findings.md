# Panda3D + Qt integration findings

This repository compares two ways to combine Panda3D rendering with a Qt user interface:

- **Native embedding**: Panda renders into a native child window hosted by Qt.
- **Offscreen rendering**: Panda renders into an offscreen buffer and Qt displays the result in a regular widget.

## Summary

At the current state of the spike:

- **Native** is the stronger path for direct Panda3D interaction.
- **Offscreen** is the stronger path for Qt-driven composition and overlays.

A practical default is:

- use **native** when camera interaction, scene picking, and Panda-centric viewport behavior are the priority
- use **offscreen** when Qt widgets must integrate tightly with the viewport area

## Native backend

### Strengths

- Direct Panda3D window ownership
- Good fit for orbit, zoom, and picking
- Fewer rendering layers between Panda and the screen
- A good baseline for interaction-heavy viewport work

### Weaknesses

- Native child windows can complicate Qt overlay composition
- Focus and activation behavior may vary by platform and window manager
- Standard Qt child widgets do not naturally stack above the embedded Panda window

### Current implementation notes

- Orbit, zoom, and picking are handled on the Panda side in native mode
- Polling Panda input avoids relying on Qt wrapper events in screen regions owned by the embedded child window

## Offscreen backend

### Strengths

- The viewport behaves like a normal Qt widget
- Qt overlays, labels, and other child widgets integrate naturally
- Composition with layouts, splitters, and standard widget hierarchies is cleaner

### Weaknesses

- More manual buffer management
- Resize handling is more delicate than with a normal Panda window
- Input mapping and frame presentation require more plumbing

### Current implementation notes

- Offscreen resize is debounced to avoid churning the Panda buffer during continuous window drags
- Qt keeps displaying the last valid frame while the resize is in progress, then refreshes to the new size once the resize settles

## Recommendation

For an interaction-first prototype or editor spike:

- **Prefer the native backend as the default**
- **Keep the offscreen backend available as a comparison path and fallback**

This keeps the shortest route to stable Panda interaction while preserving a clean path toward richer Qt composition if needed later.
