from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict, List

from backend.conversion.models import QualityIssue


MOCK_VULNERABILITIES = {
    'Microsoft.Extensions.Http': ['CVE-2023-001'],
    'Realm': ['CVE-2022-987'],
    'FirebaseAdmin': ['CVE-2021-555']
}


class VulnerabilityScanner:
    def scan_packages_config(self, packages_config: Path) -> List[QualityIssue]:
        issues: List[QualityIssue] = []
        if not packages_config.exists():
            return issues
        text = packages_config.read_text(encoding='utf-8', errors='ignore')
        for name, cves in MOCK_VULNERABILITIES.items():
            if name in text:
                for cve in cves:
                    issues.append(QualityIssue(category='security', message=f'Known vulnerability {cve} in {name}', file_path=str(packages_config), severity='warning'))
        return issues

    def scan_package_swift(self, package_swift: Path) -> List[QualityIssue]:
        issues: List[QualityIssue] = []
        if not package_swift.exists():
            return issues
        text = package_swift.read_text(encoding='utf-8', errors='ignore')
        for name, cves in MOCK_VULNERABILITIES.items():
            if name.lower() in text.lower():
                for cve in cves:
                    issues.append(QualityIssue(category='security', message=f'Known vulnerability {cve} in {name}', file_path=str(package_swift), severity='warning'))
        return issues
