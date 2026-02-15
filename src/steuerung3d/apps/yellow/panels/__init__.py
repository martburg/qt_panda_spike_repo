"""Yellow UI panel building blocks.

This package is the start of the "north" refactor:

- **VM (view model) modules** compute *what* the UI should show, without Qt.
- **Render modules** apply those VMs to actual Qt widgets.

Keeping the computation Qt-free lets us unit-test semantics and refactor
controllers aggressively without changing behavior.
"""
