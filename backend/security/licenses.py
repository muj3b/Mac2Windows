from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List

from license_expression import get_spdx_licensing

from backend.conversion.models import QualityIssue

licensing = get_spdx_licensing()

LICENSE_WARNINGS = {
    'GPL': 'GPL licenses may conflict with closed-source distribution.',
    'AGPL': 'AGPL requires releasing source for network services.',
    'LGPL': 'LGPL requires dynamic linking or disclosure of modifications.',
    'SSPL': 'SSPL is not OSI-approved and imposes strong conditions on cloud use.'
}


class LicenseScanner:
    def __init__(self) -> None:
        self.license_pattern = re.compile(r'license\s*[:=]\s*"(?P<value>[^"]+)"', re.IGNORECASE)

    def scan(self, project_root: Path) -> List[QualityIssue]:
        issues: List[QualityIssue] = []
        for potential in project_root.rglob('LICENSE*'):
            issues.extend(self._interpret_license_file(potential))
        package_json = project_root / 'package.json'
        if package_json.exists():
            issues.extend(self._scan_package_json(package_json))
        return issues

    def _interpret_license_file(self, path: Path) -> List[QualityIssue]:
        text = path.read_text(encoding='utf-8', errors='ignore')
        results: List[QualityIssue] = []
        for keyword, warning in LICENSE_WARNINGS.items():
            if keyword.lower() in text.lower():
                results.append(QualityIssue(category='license', message=warning, file_path=str(path), severity='warning'))
        return results

    def _scan_package_json(self, path: Path) -> List[QualityIssue]:
        try:
            payload = json.loads(path.read_text(encoding='utf-8'))
        except json.JSONDecodeError:
            return []
        license_field = payload.get('license') or payload.get('licenses')
        issues: List[QualityIssue] = []
        if isinstance(license_field, str):
            issues.extend(self._evaluate_expression(license_field, path))
        elif isinstance(license_field, list):
            for entry in license_field:
                if isinstance(entry, dict) and 'type' in entry:
                    issues.extend(self._evaluate_expression(entry['type'], path))
        return issues

    def _evaluate_expression(self, expression: str, path: Path) -> List[QualityIssue]:
        try:
            licensing.parse(expression)
        except Exception:  # pragma: no cover - invalid expression
            return [QualityIssue(category='license', message=f'Unrecognized license expression: {expression}', file_path=str(path), severity='warning')]
        warnings = []
        for keyword, warning in LICENSE_WARNINGS.items():
            if keyword.lower() in expression.lower():
                warnings.append(QualityIssue(category='license', message=warning, file_path=str(path), severity='warning'))
        return warnings
