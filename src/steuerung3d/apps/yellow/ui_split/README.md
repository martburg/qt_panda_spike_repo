# yellow3 UI split (edit in chunks, runtime unchanged)

This package splits the large `yellow3.ui` into three **edit-friendly** chunk files and a small **merge** tool.

## Goal
- Keep the **runtime UI identical** to the original monolithic file.
- Let you edit big pages in smaller `.ui` files.

## Files
- `yellow3_shell_marker.ui`
  - The main window + all widgets **except** the heavy tab pages.
  - Contains markers (in `whatsThis`) that tell the merge tool where to insert the parts.

- `parts/pageGuider.ui`
- `parts/pageParameters.ui`
- `parts/pageDiagnostics.ui`
  - The extracted contents of the corresponding pages.

- `merge_yellow3_ui.py`
  - Rebuilds a monolithic `yellow3.ui` by inserting each part into the correct page.

## How to use
1) Edit whichever part you need in Qt Designer:
   - `parts/pageGuider.ui`
   - `parts/pageParameters.ui`
   - `parts/pageDiagnostics.ui`

2) Rebuild the runtime file:

```bash
python merge_yellow3_ui.py --shell yellow3_shell_marker.ui --parts parts --out yellow3.ui
```

3) Use the produced `yellow3.ui` in your app exactly like before.

## Notes / invariants
- Widget `objectName`s inside each part are preserved.
- The merged output has the **same widget tree** (names/count) as the original monolithic file.


## Diagnostics split
`parts/pageDiagnostics.ui` is now a *shell* that contains the `tabsDiagnostics` structure, but each large child page is split into its own file under `parts/diagnostics/`:

- `pageDiagCommsTiming.ui`
- `pageDiagLastFrames.ui`
- `pageDiagInjection.ui`
- `pageDiagEvents.ui`
- `pageDiagLogging.ui`
- `pageParametersSet.ui`
- `pageEStopAll.ui`

The merge tool automatically assembles these back into the final `yellow3.ui`.
