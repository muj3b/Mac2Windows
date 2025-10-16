from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Dict, List

from backend.conversion.models import QualityIssue


class ValidationEngine:
    def __init__(self) -> None:
        self.dotnet_path = shutil.which('dotnet')
        self.swiftc_path = shutil.which('swiftc')

    def validate_windows_project(self, project_root: Path) -> List[QualityIssue]:
        if not self.dotnet_path:
            return [QualityIssue(category='build', message='dotnet CLI not available', severity='info')]
        solution = next(project_root.glob('*.sln'), None)
        if not solution:
            return [QualityIssue(category='build', message='Solution file not found', severity='warning')]
        process = subprocess.run([self.dotnet_path, 'build', str(solution)], capture_output=True, text=True)
        if process.returncode == 0:
            return []
        return [QualityIssue(category='build', message=process.stderr or process.stdout, severity='error')]

    def validate_mac_project(self, project_root: Path) -> List[QualityIssue]:
        if not self.swiftc_path:
            return [QualityIssue(category='build', message='swiftc not available', severity='info')]
        issues: List[QualityIssue] = []
        for swift_file in project_root.rglob('*.swift'):
            process = subprocess.run([self.swiftc_path, '-typecheck', str(swift_file)], capture_output=True, text=True)
            if process.returncode != 0:
                message = process.stderr or process.stdout
                issues.append(QualityIssue(category='build', message=message, file_path=str(swift_file), severity='error'))
        return issues
