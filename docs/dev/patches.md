# Working with patches

## Creating a patch that applies cleanly

From the repo root:

```bash
python tools/make_patch.py -o my_change.patch
```

This produces a `git apply` compatible patch with paths relative to the repo root.

## Applying a patch

```bash
git apply --whitespace=fix my_change.patch
```

If you see errors like "corrupt patch" or "No such file or directory", it is almost always caused by one of:

- patch generated from a different repo root / path prefix
- file renamed/moved since the patch was created
- CRLF/LF churn in the patch file

The repo uses `.gitattributes` to normalize line endings.
