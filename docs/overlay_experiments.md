# Overlay experiments

This note records the observed behavior of Qt overlays on top of Panda3D viewports in both integration modes.

## Child-widget overlay in offscreen mode

In offscreen mode, a Qt overlay implemented as a child widget of the viewport works as expected.

Observed behavior:

- label and text-entry widgets appear above the rendered image
- standard Qt stacking and focus behavior are preserved
- this is the most natural approach when the viewport is a regular Qt widget

## Child-widget overlay in native mode

In native embedding mode, a normal Qt child-widget overlay does not reliably appear above the Panda viewport.

Observed behavior:

- the embedded Panda child window visually dominates the viewport region
- standard Qt child widgets do not behave like true in-viewport overlays here

This is consistent with the general limitation of native-child embedding approaches: the 3D window is not just painted into the widget hierarchy like a normal child widget.

## Floating frameless overlay in native mode

A separate frameless floating Qt window positioned above the viewport works in native mode.

Observed behavior:

- the overlay can remain visible above the Panda viewport
- the overlay can host standard Qt controls such as labels and line edits
- the overlay can be repositioned on show, move, and resize events so it tracks the viewport

### Trade-off

The main downside is a small amount of follow lag while the main window is actively being moved.

This is expected because the overlay is a separate top-level window that follows the main window rather than moving as part of the same widget subtree.

## Practical takeaway

- Use **child-widget overlays** in **offscreen** mode
- Use **floating frameless overlays** in **native** mode when a small overlay is needed above the viewport
- Avoid relying on standard Qt child widgets as true overlays above a natively embedded Panda window

## Suggested policy

A practical policy for this repository is:

- **native**: default for Panda interaction and viewport behavior
- **offscreen**: preferred when integrated Qt overlays are a central requirement
- **floating overlay**: acceptable native-mode fallback for compact tools, labels, or HUD-style UI
