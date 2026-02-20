name: Drop-Compat-Shims
description: >
  Removes obsolete compatibility shims and legacy boot paths. Focus is code + tests only.
  Documentation updates are explicitly out of scope.
goals:
  - Remove unused compat shims (udp_link alias, axis_fsm fallback, legacy plc_udp config loader).
  - Remove duplicated embedded configs dir (src/steuerung3d/configs) in favor of top-level /configs.
  - Remove apps/setup_stack and all code/tests referencing it.
constraints:
  - Preserve runtime semantics (other than intentionally removing deprecated/compat paths).
  - Keep CI green: run tests and fix failures caused by removal.
  - No documentation edits (README, docs/*) unless required to keep tests building (avoid).
  - Prefer deletion over leaving dead code. If a module is removed, fix imports explicitly.
workflow:
  - Step 1: Search & impact analysis (ripgrep) before deleting.
  - Step 2: Apply minimal edits per item, commit-friendly changes.
  - Step 3: Run unit/integration tests, fix fallout.
  - Step 4: Final verification sweep (no dangling imports, no references to removed paths).
commands:
  - rg -n "steuerung3d\.protocol\.udp_link|protocol\.udp_link|UdpLink" src tests
  - rg -n "axis_fsm|from transitions|try:.*transitions|except ImportError" src tests
  - rg -n "\[plc_udp\]|plc_udp|legacy_plc_udp|_legacy_plc" src tests configs
  - rg -n "apps\.setup_stack|setup_stack|steuerung3d\.apps\.setup_stack" src tests
  - rg -n "src/steuerung3d/configs|steuerung3d/configs" src tests
verification:
  - python -m compileall src
  - pytest -q
deliverables:
  - Deletions + import fixes
  - Tests updated to avoid setup_stack wrapper
  - Remove src/steuerung3d/configs directory and references
