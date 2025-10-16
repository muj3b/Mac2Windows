from __future__ import annotations

import difflib
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def read_text_lines(path: Path) -> List[str]:
  try:
    return path.read_text(encoding='utf-8').splitlines()
  except UnicodeDecodeError:
    return path.read_text(encoding='latin-1', errors='ignore').splitlines()
  except FileNotFoundError:
    return []


def compute_diff_rows(original: List[str], converted: List[str]) -> Tuple[List[Dict[str, object]], int, int]:
  matcher = difflib.SequenceMatcher(None, original, converted)
  rows: List[Dict[str, object]] = []
  added = 0
  removed = 0
  for tag, i1, i2, j1, j2 in matcher.get_opcodes():
    if tag == 'equal':
      for offset in range(i2 - i1):
        rows.append({
          'id': len(rows),
          'type': 'context',
          'left_number': i1 + offset + 1,
          'left_text': original[i1 + offset],
          'right_number': j1 + offset + 1,
          'right_text': converted[j1 + offset]
        })
    elif tag == 'replace':
      span = max(i2 - i1, j2 - j1)
      for offset in range(span):
        left_index = i1 + offset
        right_index = j1 + offset
        left_text = original[left_index] if left_index < i2 else ''
        right_text = converted[right_index] if right_index < j2 else ''
        if left_text:
          removed += 1
        if right_text:
          added += 1
        rows.append({
          'id': len(rows),
          'type': 'replace',
          'left_number': left_index + 1 if left_text else None,
          'left_text': left_text,
          'right_number': right_index + 1 if right_text else None,
          'right_text': right_text
        })
    elif tag == 'delete':
      for offset in range(i1, i2):
        removed += 1
        rows.append({
          'id': len(rows),
          'type': 'delete',
          'left_number': offset + 1,
          'left_text': original[offset],
          'right_number': None,
          'right_text': ''
        })
    elif tag == 'insert':
      for offset in range(j1, j2):
        added += 1
        rows.append({
          'id': len(rows),
          'type': 'insert',
          'left_number': None,
          'left_text': '',
          'right_number': offset + 1,
          'right_text': converted[offset]
        })
  return rows, added, removed


def generate_diff_entry(
  original_path: Path,
  converted_path: Path,
  display_name: str,
  severity: str,
  issues: Optional[List[Dict[str, object]]] = None
) -> Dict[str, object]:
  original_lines = read_text_lines(original_path)
  converted_lines = read_text_lines(converted_path)
  rows, added, removed = compute_diff_rows(original_lines, converted_lines)
  return {
    'file_path': str(original_path),
    'target_path': str(converted_path),
    'display_name': display_name,
    'severity': severity,
    'added': added,
    'removed': removed,
    'rows': rows,
    'issues': issues or []
  }
