# yellow3 UI split (edit in chunks, runtime unchanged)

This package splits the large `yellow3.ui` into three **edit-friendly** chunk files and a small **merge** tool.

## Goal
- Keep the **runtime UI identical** to the original monolithic file.
- Let you edit big pages in smaller `.ui` files.

## Runtime UI (source of truth)
The app loads its UI from `ui_split/yellow3_merged.ui` via `ui_shell.py`.
Edit the split parts and merge to refresh that runtime file.

## Legacy duplicates (quarantined)
Older root-level UI artifacts are now in `archive_ui/`:
- `archive_ui/yellow3.ui`
- `archive_ui/yellow3_shell_marker.ui`

## Files
- `ui_split/yellow3_shell_marker.ui`
  - The main window + all widgets **except** the heavy tab pages.
  - Contains markers (in `whatsThis`) that tell the merge tool where to insert the parts.

- `ui_split/parts/pageGuider.ui`
- `ui_split/parts/pageParameters.ui`
- `ui_split/parts/pageDiagnostics.ui`
  - The extracted contents of the corresponding pages.

- `ui_split/merge_yellow3_ui.py`
  - Rebuilds `ui_split/yellow3_merged.ui` by inserting each part into the correct page.

## How to use
1) Edit whichever part you need in Qt Designer:
  - `ui_split/parts/pageGuider.ui`
  - `ui_split/parts/pageParameters.ui`
  - `ui_split/parts/pageDiagnostics.ui`

2) Rebuild the runtime file:

```bash
python ui_split/merge_yellow3_ui.py --shell ui_split/yellow3_shell_marker.ui --parts ui_split/parts --out ui_split/yellow3_merged.ui
```

3) Runtime uses `ui_split/yellow3_merged.ui`; edit parts and merge to refresh it.

## Notes / invariants
- Widget `objectName`s inside each part are preserved.
- The merged output has the **same widget tree** (names/count) as the original monolithic file.


## Architecture boundaries (Qt at the edge)
- Qt imports live only in `ui_shell.py`, `binders/`, `controllers/`, and `panels/*_render.py`.
- Pure logic lives in `domain/`, `engines/`, and `runtimes/` (Qt-free).
- HiP orchestration is handled by `runtimes/hip_runtime.py`, with policy in `engines/hip/`.


## Diagnostics split
`ui_split/parts/pageDiagnostics.ui` is now a *shell* that contains the `tabsDiagnostics` structure, but each large child page is split into its own file under `ui_split/parts/diagnostics/`:

- `pageDiagCommsTiming.ui`
- `pageDiagLastFrames.ui`
- `pageDiagInjection.ui`
- `pageDiagEvents.ui`
- `pageDiagLogging.ui`
- `pageParametersSet.ui`
- `pageEStopAll.ui`

The merge tool automatically assembles these back into the final `yellow3.ui`.
