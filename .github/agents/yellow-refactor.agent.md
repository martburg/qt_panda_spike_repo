----
name: yellow-refactor-executor
version: 1.0
goal: >
  Refactor src/steuerung3d/apps/yellow to reduce controller bloat, remove shim modules,
  introduce a Qt-free HipRuntime (mirroring DensiRuntime), and normalize widget naming.
  Must preserve runtime semantics and keep tests green.

principles:
  - No semantic drift: refactor must be behavior-preserving unless explicitly marked otherwise.
  - Qt at the edge: Qt imports only in ui_shell.py, binders/, panels/*_render.py, controllers/.
  - Pure logic in domain/, engines/, runtimes/.
  - Prefer small patches with clean checkpoints.
  - Every patch must come with a quick verification checklist.

entrypoints_to_watch:
  - python -m steuerung3d up --profile 1dev_sim
  - tests (pytest -q)

patch_slices:
  - id: A_shim_removal
    intent: "Eliminate controller shim modules by moving call sites to domain/ or engines/."
    steps:
      - "Ripgrep for imports from steuerung3d.apps.yellow.controllers.ui_* and controllers.yellow_maps and controllers.param_txn."
      - "Switch those imports to the corresponding domain/* module (or engines/* if appropriate)."
      - "Keep the shim modules temporarily, but mark them deprecated with a single-line comment."
      - "Run unit tests / minimal import check."
    acceptance:
      - "No remaining imports from controllers.ui_* in panels/*_vm.py or engines/*."
      - "App still starts (import-time) without errors."

  - id: B_hip_runtime
    intent: "Create runtimes/hip_runtime.py (Qt-free) and move orchestration from HiPController into it."
    steps:
      - "Study current HiPController.poll_once() and HipEngine.step()."
      - "Design HipRuntime API similar to DensiRuntime: collect_inputs (via binder in controller), tick() -> result."
      - "Move: staleness/age tracking, snapshot selection, engine.step call, intent list building, txn retry bookkeeping into HipRuntime."
      - "Keep HiPController as a thin wrapper: drain UDP -> runtime.tick -> binder.apply -> send intents."
      - "Ensure logging and StatusEmitter behavior preserved."
      - "Add minimal unit tests for HipRuntime (no QApplication)."
    acceptance:
      - "HiPController shrinks materially and contains no policy logic."
      - "HipRuntime imports no Qt modules."
      - "pytest -q passes (or at least existing suite + new tests pass)."

  - id: C_widget_canonicalization
    intent: "Canonicalize widget objectNames and remove Python fallbacks."
    steps:
      - "Identify all binder fallbacks (OR lookups) in binders/hip_qt_binder.py."
      - "Define canonical widget names list."
      - "Update UI split parts (ui_split/parts/*.ui) so canonical names exist."
      - "Update binder to use canonical names only; fail fast with clear error if missing."
      - "Add a small 'widget presence' test that loads merged UI and asserts key widgets exist."
    acceptance:
      - "No OR lookups for widget names remain in binder (except transitional behind a feature flag, if necessary)."
      - "UI loads and key widgets found."

  - id: D_cleanup_and_docs
    intent: "Delete shims, update docs, and leave repo in a stable, readable state."
    steps:
      - "Delete deprecated shim modules after all call sites moved."
      - "Update any local docs / README section describing yellow architecture."
      - "Optional: add short comment blocks in each folder describing boundaries (domain/ engines/ runtimes/ binders/ controllers/)."
    acceptance:
      - "No unused files; no dead imports."
      - "pytest -q green."

verification:
  smoke:
    - "python -m steuerung3d up --profile 1dev_sim (hip + densi start, no crashes)"
  tests:
    - "pytest -q"
  lint_optional:
    - "python -m compileall src/steuerung3d/apps/yellow"

deliverables:
  - "Patch slices as separate commits or clearly separated diffs."
  - "Short summary per slice: what moved, why, how verified."
  - "Any new tests added and what they cover."
