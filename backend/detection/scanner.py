from __future__ import annotations

import asyncio
import os
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set

from backend.config import Settings

LANGUAGE_EXTENSIONS = {
  '.swift': 'Swift',
  '.m': 'Objective-C',
  '.mm': 'Objective-C++',
  '.h': 'C/C++ Header',
  '.hpp': 'C++ Header',
  '.hh': 'C++ Header',
  '.c': 'C',
  '.cc': 'C++',
  '.cpp': 'C++',
  '.cxx': 'C++',
  '.cs': 'C#',
  '.vb': 'VB.NET',
  '.fs': 'F#',
  '.fsx': 'F# Script',
  '.fsi': 'F# Signature',
  '.xaml': 'XAML UI',
  '.storyboard': 'Storyboard',
  '.xib': 'XIB',
  '.plist': 'Property List'
}

MAC_FRAMEWORK_KEYWORDS = {
  'SwiftUI': ['import SwiftUI', 'SwiftUI.App'],
  'UIKit': ['import UIKit', '@UIApplicationMain'],
  'AppKit': ['import AppKit', 'NSApplicationMain'],
  'Metal': ['import Metal', 'MTLDevice'],
  'CoreData': ['import CoreData', 'NSManagedObject'],
  'Catalyst': ['macCatalyst', 'TARGET_OS_MACCATALYST']
}

WINDOWS_FRAMEWORK_KEYWORDS = {
  'WinUI 3': ['Microsoft.UI.Xaml', 'WinUI 3'],
  'WPF': ['PresentationFramework', 'System.Windows', 'xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"'],
  'WinForms': ['System.Windows.Forms'],
  'WinUI/WinAppSDK': ['WindowsAppSDK', 'Microsoft.WindowsAppSDK'],
  'Win32': ['HWND', 'CreateWindowEx'],
  '.NET MAUI': ['Microsoft.Maui', 'MauiProgram'],
  'UWP': ['Windows.UI.Xaml']
}

DEPENDENCY_PATTERNS = {
  'cocoapods': re.compile(r"pod ['\"](?P<name>[^'\"]+)['\"],?\s*['\"]?(?P<version>[^'\"]*)"),
  'swiftpm': re.compile(r'\.package\(.*name:\s*["\'](?P<name>[^"\']+)["\'].*?from:\s*["\'](?P<version>[^"\']+)["\']'),
  'nuget': re.compile(r'Include="(?P<name>[^"]+)"\s+Version="(?P<version>[^"]+)"'),
  'nuget_update': re.compile(r'<package id="(?P<name>[^"]+)" version="(?P<version>[^"]+)"'),
}

RISK_LEVELS = ['Low', 'Medium', 'High']


class ScannerError(Exception):
  """Raised when the project scanner encounters an unrecoverable error."""


@dataclass
class LanguageStats:
  files: int = 0
  lines: int = 0


@dataclass
class ScanContext:
  project_root: Path
  direction: Optional[str]
  settings: Settings
  total_files: int = 0
  total_lines: int = 0
  total_bytes: int = 0
  languages: Dict[str, LanguageStats] = field(default_factory=lambda: defaultdict(LanguageStats))
  mac_frameworks: Dict[str, Dict[str, Any]] = field(default_factory=dict)
  windows_frameworks: Dict[str, Dict[str, Any]] = field(default_factory=dict)
  dependencies: Dict[str, Dict[str, Any]] = field(default_factory=dict)
  build_configs: Set[str] = field(default_factory=set)
  mixed_languages: bool = False


class ProjectScanner:
  def __init__(self, settings: Settings) -> None:
    self.settings = settings

  async def scan(self, project_path: str, direction: Optional[str] = None) -> Dict[str, Any]:
    path = Path(project_path).expanduser().resolve()
    if not path.exists() or not path.is_dir():
      raise ScannerError(f'Project path not found or not a directory: {path}')

    context = ScanContext(project_root=path, direction=direction, settings=self.settings)
    result = await asyncio.to_thread(self._scan_sync, context)
    return result

  def _scan_sync(self, context: ScanContext) -> Dict[str, Any]:
    for root, _, files in os.walk(context.project_root):
      for filename in files:
        file_path = Path(root) / filename
        self._process_file(file_path, context)

    language_list = [
      {'name': lang, 'files': stats.files, 'lines': stats.lines}
      for lang, stats in context.languages.items()
    ]
    language_list.sort(key=lambda item: item['lines'], reverse=True)

    context.mixed_languages = len(language_list) > 1

    summary = self._build_summary(context)
    analysis = self._build_analysis(context, summary)
    suggested_targets = self._suggest_targets(context, language_list)

    mac_frameworks = []
    for framework in context.mac_frameworks.values():
      mac_frameworks.append(
        {
          'name': framework['name'],
          'version': framework.get('version'),
          'evidence': sorted(framework.get('evidence', []))
        }
      )
    windows_frameworks = []
    for framework in context.windows_frameworks.values():
      windows_frameworks.append(
        {
          'name': framework['name'],
          'version': framework.get('version'),
          'evidence': sorted(framework.get('evidence', []))
        }
      )

    return {
      'project_path': str(context.project_root),
      'direction': context.direction or 'mac-to-win',
      'summary': summary,
      'languages': language_list,
      'frameworks': {
        'mac': mac_frameworks,
        'windows': windows_frameworks
      },
      'dependencies': list(context.dependencies.values()),
      'build_configs': sorted(context.build_configs),
      'mixed_languages': context.mixed_languages,
      'analysis': analysis,
      'suggested_targets': suggested_targets
    }

  def _process_file(self, file_path: Path, context: ScanContext) -> None:
    context.total_files += 1
    try:
      context.total_bytes += file_path.stat().st_size
    except (OSError, ValueError):
      pass

    extension = file_path.suffix.lower()
    language = LANGUAGE_EXTENSIONS.get(extension)
    if language:
      lines = self._safe_line_count(file_path, context.settings.max_line_count_bytes)
      stats = context.languages[language]
      stats.files += 1
      stats.lines += lines
      context.total_lines += lines
      self._detect_frameworks(file_path, language, context)

    self._detect_dependency_files(file_path, context)
    self._detect_build_configs(file_path, context)

  def _detect_dependency_files(self, file_path: Path, context: ScanContext) -> None:
    name = file_path.name.lower()

    if name == 'podfile':
      self._parse_cocoapods(file_path, context)
    elif name == 'package.swift':
      self._parse_swiftpm(file_path, context)
    elif file_path.suffix.lower() in {'.csproj', '.fsproj', '.vbproj'}:
      self._parse_nuget(file_path, context)
    elif name == 'packages.config':
      self._parse_nuget_packages_config(file_path, context)
    elif file_path.suffix.lower() in {'.sln', '.xcworkspace', '.xcproj', '.xcconfig'}:
      context.build_configs.add(file_path.name)

  def _parse_cocoapods(self, file_path: Path, context: ScanContext) -> None:
    try:
      text = file_path.read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError):
      return

    for match in DEPENDENCY_PATTERNS['cocoapods'].finditer(text):
      name = match.group('name')
      version = match.group('version') or None
      key = f'cocoapods::{name}'
      context.dependencies[key] = {
        'name': name,
        'manager': 'CocoaPods',
        'version': version
      }

  def _parse_swiftpm(self, file_path: Path, context: ScanContext) -> None:
    try:
      text = file_path.read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError):
      return

    for match in DEPENDENCY_PATTERNS['swiftpm'].finditer(text):
      name = match.group('name')
      version = match.group('version')
      key = f'swiftpm::{name}'
      context.dependencies[key] = {
        'name': name,
        'manager': 'SwiftPM',
        'version': version
      }

  def _parse_nuget(self, file_path: Path, context: ScanContext) -> None:
    try:
      text = file_path.read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError):
      return
    for match in DEPENDENCY_PATTERNS['nuget'].finditer(text):
      name = match.group('name')
      version = match.group('version')
      key = f'nuget::{name}'
      context.dependencies[key] = {
        'name': name,
        'manager': 'NuGet',
        'version': version
      }

  def _parse_nuget_packages_config(self, file_path: Path, context: ScanContext) -> None:
    try:
      text = file_path.read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError):
      return
    for match in DEPENDENCY_PATTERNS['nuget_update'].finditer(text):
      name = match.group('name')
      version = match.group('version')
      key = f'nuget::{name}'
      context.dependencies[key] = {
        'name': name,
        'manager': 'NuGet',
        'version': version
      }

  def _detect_frameworks(self, file_path: Path, language: str, context: ScanContext) -> None:
    preview = self._read_preview(file_path, context.settings.max_preview_bytes)
    if not preview:
      return

    if language in {'Swift', 'Objective-C', 'Objective-C++', 'C/C++ Header', 'C++ Header'}:
      matches = self._match_keywords(preview, MAC_FRAMEWORK_KEYWORDS)
      for framework in matches:
        context.mac_frameworks.setdefault(
          framework,
          {'name': framework, 'version': None, 'evidence': set()}
        )['evidence'].add(str(file_path))

    if language in {'C#', 'VB.NET', 'F#', 'XAML UI'}:
      matches = self._match_keywords(preview, WINDOWS_FRAMEWORK_KEYWORDS)
      for framework in matches:
        context.windows_frameworks.setdefault(
          framework,
          {'name': framework, 'version': None, 'evidence': set()}
        )['evidence'].add(str(file_path))

  def _detect_build_configs(self, file_path: Path, context: ScanContext) -> None:
    name = file_path.name
    if name.endswith(('.sln', '.xcworkspace', '.xcproj', '.xcconfig', '.vcxproj')):
      context.build_configs.add(name)

  def _safe_line_count(self, file_path: Path, max_bytes: int) -> int:
    try:
      if file_path.stat().st_size > max_bytes:
        return 0
      with file_path.open('r', encoding='utf-8', errors='ignore') as handle:
        return sum(1 for _ in handle)
    except (OSError, UnicodeDecodeError):
      return 0

  def _read_preview(self, file_path: Path, max_bytes: int) -> str:
    try:
      with file_path.open('r', encoding='utf-8', errors='ignore') as handle:
        return handle.read(max_bytes)
    except (OSError, UnicodeDecodeError):
      return ''

  def _match_keywords(self, text: str, catalog: Dict[str, Iterable[str]]) -> List[str]:
    matches = []
    for framework, keywords in catalog.items():
      if any(keyword in text for keyword in keywords):
        matches.append(framework)
    return matches

  def _build_summary(self, context: ScanContext) -> Dict[str, Any]:
    estimated_minutes = max(5, int(context.total_lines / 120)) if context.total_lines else 5
    estimated_tokens = max(5000, context.total_lines * 12)
    estimated_cost = round(estimated_tokens * 0.000018, 2)
    return {
      'total_files': context.total_files,
      'total_lines': context.total_lines,
      'total_bytes': context.total_bytes,
      'estimated_minutes': estimated_minutes,
      'estimated_tokens': estimated_tokens,
      'estimated_cost_usd': estimated_cost
    }

  def _build_analysis(self, context: ScanContext, summary: Dict[str, Any]) -> Dict[str, Any]:
    language_mix = len(context.languages)
    frameworks_detected = len(context.mac_frameworks) + len(context.windows_frameworks)
    risk_index = 1
    if language_mix > 3 or frameworks_detected > 4:
      risk_index = 2
    elif language_mix <= 1 and frameworks_detected <= 2:
      risk_index = 0

    base_analysis = {
      'auto_convertible': 0.85,
      'manual_review': 0.10,
      'unsupported': 0.05
    }

    if risk_index == 2:
      base_analysis = {'auto_convertible': 0.72, 'manual_review': 0.20, 'unsupported': 0.08}
    elif risk_index == 0:
      base_analysis = {'auto_convertible': 0.9, 'manual_review': 0.07, 'unsupported': 0.03}

    return {
      **base_analysis,
      'risk_level': RISK_LEVELS[risk_index],
      'time_estimate_minutes': summary['estimated_minutes'],
      'estimated_tokens': summary['estimated_tokens'],
      'estimated_cost_usd': summary['estimated_cost_usd']
    }

  def _suggest_targets(
    self,
    context: ScanContext,
    languages: List[Dict[str, Any]]
  ) -> List[Dict[str, str]]:
    direction = context.direction or 'mac-to-win'
    suggestions: List[Dict[str, str]] = []

    if direction == 'mac-to-win':
      suggestions = [
        {'id': 'winui3', 'label': 'WinUI 3 (.NET 8)', 'reason': 'Modern Windows UX'},
        {'id': 'wpf', 'label': 'WPF (.NET 8)', 'reason': 'Desktop parity'},
        {'id': 'maui', 'label': '.NET MAUI', 'reason': 'Cross-platform target'}
      ]
    else:
      suggestions = [
        {'id': 'swiftui', 'label': 'SwiftUI', 'reason': 'Modern macOS UI'},
        {'id': 'appkit', 'label': 'AppKit', 'reason': 'Legacy macOS'},
        {'id': 'catalyst', 'label': 'Mac Catalyst', 'reason': 'Shared iOS/macOS'}
      ]

    top_language = languages[0]['name'] if languages else None
    if top_language == 'C++':
      suggestions.append({'id': 'cpp-shared', 'label': 'Shared C++ core', 'reason': 'Common core'})

    return suggestions
