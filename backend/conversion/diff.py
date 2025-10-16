from __future__ import annotations

import difflib
from pathlib import Path


def generate_side_by_side(original: Path, converted: Path, destination: Path) -> Path:
    original_lines = original.read_text(encoding='utf-8', errors='ignore').splitlines()
    converted_lines = converted.read_text(encoding='utf-8', errors='ignore').splitlines()
    html = difflib.HtmlDiff(tabsize=2, wrapcolumn=120).make_file(original_lines, converted_lines, fromdesc=str(original), todesc=str(converted))
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(html, encoding='utf-8')
    return destination
