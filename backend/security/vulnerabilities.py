from __future__ import annotations

import asyncio
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List

from backend.conversion.models import QualityIssue
from backend.security.osv_client import OSVClient, VulnerabilityRecord


class VulnerabilityScanner:
    def __init__(self) -> None:
        self.client = OSVClient()

    async def scan_packages_config(self, packages_config: Path) -> List[QualityIssue]:
        if not packages_config.exists():
            return []
        deps = self._parse_nuget_packages(packages_config)
        records = await self.client.query_multiple({name: 'NuGet' for name in deps})
        return self._records_to_issues(records, packages_config)

    async def scan_package_swift(self, package_swift: Path) -> List[QualityIssue]:
        if not package_swift.exists():
            return []
        deps = self._parse_swiftpm(package_swift)
        records = await self.client.query_multiple({name: 'SwiftPM' for name in deps})
        return self._records_to_issues(records, package_swift)

    def _records_to_issues(self, records: Dict[str, List[VulnerabilityRecord]], source_path: Path) -> List[QualityIssue]:
        issues: List[QualityIssue] = []
        for package, vulns in records.items():
            for vuln in vulns:
                severity = vuln.severity or 'unknown'
                message = f"{package}: {vuln.identifier} ({severity}) - {vuln.summary}"
                issues.append(QualityIssue(category='security', message=message, file_path=str(source_path), severity='warning'))
        return issues

    def _parse_nuget_packages(self, packages_config: Path) -> List[str]:
        try:
            tree = ET.parse(packages_config)
        except ET.ParseError:
            return []
        return [pkg.attrib.get('id', '') for pkg in tree.findall('package') if pkg.attrib.get('id')]

    def _parse_swiftpm(self, package_swift: Path) -> List[str]:
        text = package_swift.read_text(encoding='utf-8', errors='ignore')
        deps: List[str] = []
        for line in text.splitlines():
            if '.package' in line:
                parts = line.split('name:')
                if len(parts) > 1:
                    name_part = parts[1].split(',')[0]
                    name = name_part.replace('"', '').strip()
                    if name:
                        deps.append(name)
        return deps
