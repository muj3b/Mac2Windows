from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import psutil


@dataclass
class TestRunResult:
  framework: str
  command: List[str]
  duration_seconds: float
  stdout: str
  stderr: str
  status: str
  failures: List[str] = field(default_factory=list)
  todo: List[str] = field(default_factory=list)
  skipped_reason: Optional[str] = None


class TestHarness:
  """Execute converted test suites and collect actionable feedback."""

  def __init__(self) -> None:
    self.dotnet_path = shutil.which('dotnet')
    self.swift_path = shutil.which('swift')

  def run(self, session) -> Optional[TestRunResult]:
    if session.direction == 'mac-to-win':
      return self._run_dotnet_tests(session.target_path)
    return self._run_swift_tests(session.target_path)

  def _run_dotnet_tests(self, project_root: Path) -> TestRunResult:
    if not self.dotnet_path:
      return TestRunResult(
        framework='dotnet',
        command=['dotnet', 'test'],
        duration_seconds=0.0,
        stdout='',
        stderr='',
        status='skipped',
        skipped_reason='dotnet CLI not available on host'
      )
    solution = _discover_solution(project_root)
    command = [self.dotnet_path, 'test']
    if solution:
      command.append(str(solution))
    start = time.perf_counter()
    process = psutil.Popen(command, cwd=str(project_root), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    stdout, stderr = process.communicate()
    duration = time.perf_counter() - start
    exit_code = process.returncode or 0
    failures = _parse_dotnet_failures(stdout + '\n' + stderr)
    status = 'passed' if exit_code == 0 else 'failed'
    return TestRunResult(
      framework='dotnet',
      command=command,
      duration_seconds=max(duration, 0.0),
      stdout=stdout,
      stderr=stderr,
      status=status,
      failures=failures,
      todo=_todo_from_failures(failures)
    )

  def _run_swift_tests(self, project_root: Path) -> TestRunResult:
    if not self.swift_path:
      return TestRunResult(
        framework='swift',
        command=['swift', 'test'],
        duration_seconds=0.0,
        stdout='',
        stderr='',
        status='skipped',
        skipped_reason='swift toolchain not available on host'
      )
    command = [self.swift_path, 'test']
    start = time.perf_counter()
    process = psutil.Popen(command, cwd=str(project_root), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    stdout, stderr = process.communicate()
    duration = time.perf_counter() - start
    exit_code = process.returncode or 0
    output = stdout + '\n' + stderr
    failures = _parse_swift_failures(output)
    status = 'passed' if exit_code == 0 else 'failed'
    return TestRunResult(
      framework='swift',
      command=command,
      duration_seconds=max(duration, 0.0),
      stdout=stdout,
      stderr=stderr,
      status=status,
      failures=failures,
      todo=_todo_from_failures(failures)
    )


def _discover_solution(project_root: Path) -> Optional[Path]:
  for suffix in ('*.sln', '*.csproj', '*.vbproj', '*.fsproj'):
    candidate = next(project_root.glob(suffix), None)
    if candidate:
      return candidate
  tests_dir = project_root / 'tests'
  if tests_dir.exists():
    return _discover_solution(tests_dir)
  return None


DOTNET_FAILURE_RE = re.compile(r'Failed\s+([A-Za-z0-9_\.\(\)]+)\s+\[(.+?)\]')
SWIFT_FAILURE_RE = re.compile(r"Test Case '-\[([^\]]+)\]' failed")


def _parse_dotnet_failures(output: str) -> List[str]:
  matches: List[str] = []
  for line in output.splitlines():
    match = DOTNET_FAILURE_RE.search(line)
    if match:
      matches.append(f'{match.group(1)} ({match.group(2)})')
  return matches


def _parse_swift_failures(output: str) -> List[str]:
  lines: List[str] = []
  for line in output.splitlines():
    if 'failed' not in line:
      continue
    match = SWIFT_FAILURE_RE.search(line)
    if match:
      lines.append(match.group(1))
  return lines


def _todo_from_failures(failures: List[str]) -> List[str]:
  todos = []
  for failure in failures:
    todos.append(f'Investigate failing test: {failure}')
  return todos
