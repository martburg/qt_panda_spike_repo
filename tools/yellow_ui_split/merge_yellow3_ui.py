#!/usr/bin/env python
"""Merge split Qt Designer .ui parts back into a single yellow3.ui.

- The *shell* file contains the full QMainWindow structure, but the heavy pages
  (pageGuider/pageParameters/pageDiagnostics) are emptied and tagged with
  property whatsThis="__PART__:pageX".

- Each part file is a standalone QWidget form containing the original content of that page.

This produces a runtime .ui identical in widget tree (no extra host widgets).
"""

from __future__ import annotations

import argparse
import xml.etree.ElementTree as ET
from pathlib import Path

PAGE_NAMES = ["pageGuider", "pageParameters", "pageDiagnostics"]

# Diagnostics sub-pages (children of the Diagnostics tab widget)
SUBPAGE_NAMES = [
    "pageDiagCommsTiming",
    "pageDiagLastFrames",
    "pageDiagInjection",
    "pageDiagEvents",
    "pageDiagLogging",
    "pageParametersSet",
    "pageEStopAll",
]


def _find_widget_by_name(root: ET.Element, name: str) -> ET.Element | None:
    for w in root.iter("widget"):
        if w.get("name") == name:
            return w
    return None


def _load_part(parts_dir: Path, page_name: str) -> ET.Element:
    part_path = parts_dir / f"{page_name}.ui"
    if not part_path.exists():
        raise FileNotFoundError(part_path)
    pr = ET.parse(part_path).getroot()
    # root is <ui>; first widget child is the form root widget
    w = pr.find("widget")
    if w is None:
        raise ValueError(f"No root widget in {part_path}")
    return w


def _load_subpart(parts_dir: Path, page_name: str) -> ET.Element:
    sub_dir = parts_dir / "diagnostics"
    part_path = sub_dir / f"{page_name}.ui"
    if not part_path.exists():
        raise FileNotFoundError(part_path)
    pr = ET.parse(part_path).getroot()
    w = pr.find("widget")
    if w is None:
        raise ValueError(f"No root widget in {part_path}")
    return w


def _clear_children(el: ET.Element) -> None:
    for c in list(el):
        el.remove(c)


def _clone_children(src: ET.Element, dst: ET.Element) -> None:
    """Copy children from src into dst (deep copy)."""
    for child in list(src):
        dst.append(ET.fromstring(ET.tostring(child, encoding="utf-8")))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shell", required=True, type=Path)
    ap.add_argument("--parts", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    sr = ET.parse(args.shell).getroot()

    for page in PAGE_NAMES:
        page_w = _find_widget_by_name(sr, page)
        if page_w is None:
            raise SystemExit(f"Shell missing {page}")

        # verify marker (optional)
        marker_ok = False
        for prop in page_w.findall("property"):
            if prop.get("name") == "whatsThis":
                s = prop.find("string")
                if s is not None and (s.text or "").strip() == f"__PART__:{page}":
                    marker_ok = True
                    break

        # Load part
        part_root_widget = _load_part(args.parts, page)

        # Clear page children and inject part children
        _clear_children(page_w)
        _clone_children(part_root_widget, page_w)

        # Ensure marker property removed from runtime output
        for prop in list(page_w.findall("property")):
            if prop.get("name") == "whatsThis":
                page_w.remove(prop)

    # Merge diagnostics sub-pages if present in shell/parts
    for page in SUBPAGE_NAMES:
        page_w = _find_widget_by_name(sr, page)
        if page_w is None:
            continue

        marker_ok = False
        for prop in page_w.findall("property"):
            if prop.get("name") == "whatsThis":
                s = prop.find("string")
                if s is not None and (s.text or "").strip() == f"__PART__:{page}":
                    marker_ok = True
                    break

        if not marker_ok:
            continue

        part_root_widget = _load_subpart(args.parts, page)
        _clear_children(page_w)
        _clone_children(part_root_widget, page_w)

        for prop in list(page_w.findall("property")):
            if prop.get("name") == "whatsThis":
                page_w.remove(prop)

    ET.indent(sr, space=" ", level=0)
    ET.ElementTree(sr).write(args.out, encoding="utf-8", xml_declaration=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
