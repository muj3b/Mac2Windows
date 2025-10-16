from __future__ import annotations

import time
from pathlib import Path
from typing import Dict


def run_benchmarks(mac_project: Path, win_project: Path) -> Dict[str, float]:
  # Placeholder benchmark simulating timing.
  start = time.time()
  mac_duration = _count_lines(mac_project)
  win_duration = _count_lines(win_project)
  return {
    'mac_duration': mac_duration,
    'win_duration': win_duration,
    'timestamp': time.time() - start
  }


def _count_lines(project: Path) -> float:
  total = 0
  for file_path in project.rglob('*'):
    if not file_path.is_file():
      continue
    try:
      total += len(file_path.read_text(encoding='utf-8', errors='ignore').splitlines())
    except OSError:
      continue
  return total / 1000.0
