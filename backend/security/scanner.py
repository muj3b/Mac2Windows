from __future__ import annotations

import json
from pathlib import Path
from typing import List

from backend.conversion.models import QualityIssue


VULNERABLE_DEPENDENCIES = {
  'log4j': 'CVE-2021-44228',
  'oldfirebase': 'Outdated Firebase SDK'
}


LICENSE_MAP = {
  'GPL': 'Copyleft license may conflict with target project policies.',
  'AGPL': 'Copyleft license may conflict with target project policies.'
}


def scan_dependency_file(file_path: Path) -> List[QualityIssue]:
  issues: List[QualityIssue] = []
  try:
    text = file_path.read_text(encoding='utf-8', errors='ignore')
  except OSError:
    return issues
  lowered = text.lower()
  for dep, description in VULNERABLE_DEPENDENCIES.items():
    if dep in lowered:
      issues.append(
        QualityIssue(
          category='security',
          message=f'Dependency {dep} flagged: {description}',
          severity='warning',
          file_path=str(file_path)
        )
      )
  for license_name, warning in LICENSE_MAP.items():
    if license_name.lower() in lowered:
      issues.append(
        QualityIssue(
          category='license',
          message=f'License {license_name}: {warning}',
          severity='info',
          file_path=str(file_path)
        )
      )
  return issues
