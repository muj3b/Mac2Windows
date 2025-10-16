from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List

from backend.conversion.models import QualityIssue


LICENSE_WARNINGS = {
    'gpl': 'GPL licenses may conflict with closed-source distribution.',
    'agpl': 'AGPL licenses require source disclosure for network services.',
    'lgpl': 'LGPL requires dynamic linking or source disclosure of modifications.'
}


class LicenseScanner:
    def scan(self, project_root: Path) -> List[QualityIssue]:
        issues: List[QualityIssue] = []
        license_files = list(project_root.rglob('LICENSE')) + list(project_root.rglob('LICENSE.*'))
        for license_file in license_files:
            content = license_file.read_text(encoding='utf-8', errors='ignore').lower()
            for keyword, warning in LICENSE_WARNINGS.items():
                if keyword in content:
                    issues.append(QualityIssue(category='license', message=warning, file_path=str(license_file), severity='warning'))

        package_json = project_root / 'package.json'
        if package_json.exists():
            try:
                data = json.loads(package_json.read_text(encoding='utf-8'))
                license_field = (data.get('license') or '').lower()
                for keyword, warning in LICENSE_WARNINGS.items():
                    if keyword in license_field:
                        issues.append(QualityIssue(category='license', message=warning, file_path=str(package_json), severity='warning'))
            except json.JSONDecodeError:
                pass
        return issues
