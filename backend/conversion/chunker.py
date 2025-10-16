from __future__ import annotations

import itertools
import re
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

from backend.conversion.models import ChunkWorkItem, Stage, STAGE_ORDER
from backend.detection.scanner import LANGUAGE_EXTENSIONS

CODE_EXTENSIONS = {ext for ext, name in LANGUAGE_EXTENSIONS.items() if 'UI' not in name}
RESOURCE_EXTENSIONS = {
  '.xcassets',
  '.storyboard',
  '.xib',
  '.plist',
  '.strings',
  '.resx',
  '.png',
  '.jpg',
  '.jpeg',
  '.gif',
  '.svg',
  '.mp4',
  '.mov'
}
TEST_HINTS = {'Tests', 'Test', 'Specs', 'Spec'}

IMPORT_PATTERNS = {
  '.swift': re.compile(r'^\s*import\s+([A-Za-z0-9_\.]+)', re.MULTILINE),
  '.m': re.compile(r'^\s*@import\s+([A-Za-z0-9_\.]+);', re.MULTILINE),
  '.mm': re.compile(r'^\s*@import\s+([A-Za-z0-9_\.]+);', re.MULTILINE),
  '.h': re.compile(r'^\s*@class\s+([A-Za-z0-9_]+);', re.MULTILINE),
  '.hpp': re.compile(r'^\s*#include\s+[<"]([A-Za-z0-9_\/\.]+)[">]', re.MULTILINE),
  '.cpp': re.compile(r'^\s*#include\s+[<"]([A-Za-z0-9_\/\.]+)[">]', re.MULTILINE),
  '.cs': re.compile(r'^\s*using\s+([A-Za-z0-9_\.]+);', re.MULTILINE),
  '.fs': re.compile(r'^\s*open\s+([A-Za-z0-9_\.]+)', re.MULTILINE),
  '.vb': re.compile(r'^\s*Imports\s+([A-Za-z0-9_\.]+)', re.MULTILINE)
}

FUNCTION_PATTERNS = {
  '.swift': re.compile(r'^\s*(?:func|struct|class|enum)\s+[A-Za-z0-9_]+', re.MULTILINE),
  '.m': re.compile(r'^\s*[-+]\s*\([^)]+\)\s*[A-Za-z0-9_]+', re.MULTILINE),
  '.mm': re.compile(r'^\s*[-+]\s*\([^)]+\)\s*[A-Za-z0-9_]+', re.MULTILINE),
  '.cs': re.compile(r'^\s*(?:public|private|internal|protected)?\s*(?:async\s+)?(?:[\w<>\[\]]+\s+)+[A-Za-z0-9_]+\s*\(', re.MULTILINE),
  '.cpp': re.compile(r'^\s*[A-Za-z0-9_:<>\*&]+\s+[A-Za-z0-9_]+\s*\(', re.MULTILINE),
  '.fs': re.compile(r'^\s*let\s+[A-Za-z0-9_]+\s*=', re.MULTILINE)
}

MAX_CHUNK_LINES = 120
MIN_CHUNK_LINES = 30


@dataclass
class DependencyGraph:
  adjacency: Dict[Path, List[Path]]

  def topological_sort(self) -> List[Path]:
    indegree: Dict[Path, int] = defaultdict(int)
    for node, neighbors in self.adjacency.items():
      indegree.setdefault(node, 0)
      for neighbor in neighbors:
        indegree[neighbor] += 1

    queue = deque(sorted([node for node, deg in indegree.items() if deg == 0], key=str))
    ordered: List[Path] = []

    while queue:
      node = queue.popleft()
      ordered.append(node)
      for neighbor in self.adjacency.get(node, []):
        indegree[neighbor] -= 1
        if indegree[neighbor] == 0:
          queue.append(neighbor)

    remaining = [node for node, deg in indegree.items() if deg > 0]
    if remaining:
      ordered.extend(sorted(remaining, key=str))

    return ordered


def collect_project_files(root: Path) -> List[Path]:
  files: List[Path] = []
  for path in root.rglob('*'):
    if path.is_file():
      files.append(path)
  return files


def classify_stage(file_path: Path, direction: str) -> Stage:
  suffix = file_path.suffix.lower()
  relative = file_path.name.lower()

  if suffix in RESOURCE_EXTENSIONS or any(
    token in file_path.parts for token in ('Assets.xcassets', 'Resources', 'resource')
  ):
    return Stage.RESOURCES

  if relative in {'podfile', 'package.swift', 'packages.config', 'nuget.config'} or suffix in {
    '.csproj',
    '.fsproj',
    '.vbproj',
    '.sln',
    '.xcproj',
    '.xcodeproj'
  }:
    return Stage.DEPENDENCIES

  if suffix in CODE_EXTENSIONS:
    return Stage.CODE

  if any(hint.lower() in file_path.name.lower() for hint in TEST_HINTS):
    return Stage.TESTS

  return Stage.CODE


def build_dependency_graph(files: Iterable[Path]) -> DependencyGraph:
  adjacency: Dict[Path, List[Path]] = defaultdict(list)
  index: Dict[str, Path] = {}
  for file_path in files:
    index[str(file_path)] = file_path

  for file_path in files:
    suffix = file_path.suffix.lower()
    pattern = IMPORT_PATTERNS.get(suffix)
    if not pattern:
      continue
    try:
      text = file_path.read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError):
      continue
    neighbors: List[Path] = []
    for match in pattern.findall(text):
      candidate = match.split('.')[0]
      for other_path in files:
        if other_path == file_path:
          continue
        if candidate in other_path.name:
          neighbors.append(other_path)
          break
    if neighbors:
      adjacency[file_path] = neighbors
  return DependencyGraph(adjacency=dict(adjacency))


def split_into_chunks(
  file_path: Path, stage: Stage, language: str, max_lines: int = MAX_CHUNK_LINES
) -> Iterator[ChunkWorkItem]:
  try:
    text = file_path.read_text(encoding='utf-8')
  except (OSError, UnicodeDecodeError):
    return iter([])

  lines = text.splitlines()
  total_lines = len(lines)
  if total_lines <= max_lines:
    chunk = ChunkWorkItem(
      file_path=file_path,
      language=language,
      start_line=1,
      end_line=total_lines,
      content=text,
      stage=stage,
      chunk_id=_chunk_id(file_path, 0)
    )
    return iter([chunk])

  function_boundaries = _detect_function_boundaries(text, file_path.suffix.lower())
  segments = _group_lines_by_boundaries(function_boundaries, total_lines, max_lines)

  items: List[ChunkWorkItem] = []
  for index, (start, end) in enumerate(segments):
    content = '\n'.join(lines[start - 1:end])
    symbols = [sym for sym, s, e in function_boundaries if s >= start and e <= end]
    items.append(
      ChunkWorkItem(
        file_path=file_path,
        language=language,
        start_line=start,
        end_line=end,
        content=content,
        symbols=symbols,
        stage=stage,
        chunk_id=_chunk_id(file_path, index)
      )
    )
  return iter(items)


def _detect_function_boundaries(text: str, suffix: str) -> List[Tuple[str, int, int]]:
  pattern = FUNCTION_PATTERNS.get(suffix)
  if not pattern:
    return []

  matches = list(pattern.finditer(text))
  boundaries: List[Tuple[str, int, int]] = []
  lines = text.splitlines()

  for index, match in enumerate(matches):
    start_pos = match.start()
    start_line = text[:start_pos].count('\n') + 1
    end_line = len(lines)
    if index + 1 < len(matches):
      next_pos = matches[index + 1].start()
      end_line = text[:next_pos].count('\n')
    symbol_name = match.group(0).strip().split()[1]
    boundaries.append((symbol_name, start_line, max(end_line, start_line)))
  return boundaries


def _group_lines_by_boundaries(
  boundaries: Sequence[Tuple[str, int, int]], total_lines: int, max_lines: int
) -> List[Tuple[int, int]]:
  if not boundaries:
    chunk_ranges = []
    start = 1
    while start <= total_lines:
      end = min(total_lines, start + max_lines - 1)
      chunk_ranges.append((start, end))
      start = end + 1
    return chunk_ranges

  ranges: List[Tuple[int, int]] = []
  current_start = boundaries[0][1]
  current_end = boundaries[0][2]
  for _, start, end in boundaries[1:]:
    if end - current_start >= max_lines:
      ranges.append((current_start, current_end))
      current_start = start
    current_end = end
  ranges.append((current_start, min(total_lines, current_end)))
  return ranges


def _chunk_id(file_path: Path, index: int) -> str:
  sanitized = '-'.join(part.replace(' ', '_') for part in file_path.parts[-3:])
  return f'{sanitized}:{index}'


def generate_work_plan(project_root: Path, direction: str) -> Dict[Stage, List[ChunkWorkItem]]:
  files = collect_project_files(project_root)

  stage_map: Dict[Stage, List[ChunkWorkItem]] = {stage: [] for stage in STAGE_ORDER}

  resource_targets = _filter_resources(files, direction)
  asset_directories = [path for path in project_root.rglob('*.xcassets') if path.is_dir()]
  for file_path in resource_targets:
    stage_map[Stage.RESOURCES].append(
      ChunkWorkItem(
        file_path=file_path,
        language='resource',
        start_line=1,
        end_line=0,
        content='',
        stage=Stage.RESOURCES,
        chunk_id=_chunk_id(file_path, 0)
      )
    )
  for index, dir_path in enumerate(asset_directories):
    stage_map[Stage.RESOURCES].append(
      ChunkWorkItem(
        file_path=dir_path,
        language='asset-bundle',
        start_line=0,
        end_line=0,
        content='',
        stage=Stage.RESOURCES,
        chunk_id=_chunk_id(dir_path, index)
      )
    )

  dependency_targets = _filter_dependencies(files, direction)
  for file_path in dependency_targets:
    stage_map[Stage.DEPENDENCIES].append(
      ChunkWorkItem(
        file_path=file_path,
        language='config',
        start_line=1,
        end_line=0,
        content='',
        stage=Stage.DEPENDENCIES,
        chunk_id=_chunk_id(file_path, 0)
      )
    )

  stage_map[Stage.PROJECT_SETUP] = _project_setup_tasks(project_root, direction)
  stage_map[Stage.TESTS] = _test_tasks(files, direction)

  code_files = [
    path
    for path in files
    if classify_stage(path, direction) == Stage.CODE and path.suffix.lower() in CODE_EXTENSIONS
  ]
  dependency_graph = build_dependency_graph(code_files)
  for file_path in dependency_graph.topological_sort():
    language = LANGUAGE_EXTENSIONS.get(file_path.suffix.lower(), 'code')
    for chunk in split_into_chunks(file_path, Stage.CODE, language):
      stage_map[Stage.CODE].append(chunk)

  return stage_map


def _filter_resources(files: Iterable[Path], direction: str) -> List[Path]:
  resources = []
  for file_path in files:
    suffix = file_path.suffix.lower()
    if suffix in RESOURCE_EXTENSIONS:
      resources.append(file_path)
      continue
    if direction == 'mac-to-win' and file_path.name in {'Info.plist'}:
      resources.append(file_path)
    if direction == 'win-to-mac' and suffix in {'.resw', '.resjson'}:
      resources.append(file_path)
  return sorted(resources)


def _filter_dependencies(files: Iterable[Path], direction: str) -> List[Path]:
  targets = []
  for file_path in files:
    name = file_path.name.lower()
    suffix = file_path.suffix.lower()
    if direction == 'mac-to-win':
      if name in {'podfile', 'package.swift'} or suffix in {'.xcworkspace', '.xcproj'}:
        targets.append(file_path)
    else:
      if suffix in {'.csproj', '.fsproj', '.vbproj', '.sln'} or name in {'packages.config', 'nuget.config'}:
        targets.append(file_path)
  return sorted(targets)


def _project_setup_tasks(project_root: Path, direction: str) -> List[ChunkWorkItem]:
  tasks: List[ChunkWorkItem] = []
  labels = [
    ('structure', 'Generate target folder structure'),
    ('solution', 'Create solution/workspace definition'),
    ('tooling', 'Sync toolchain configuration')
  ]
  for index, (identifier, description) in enumerate(labels):
    tasks.append(
      ChunkWorkItem(
        file_path=project_root / f'.pipeline/{identifier}',
        language='task',
        start_line=0,
        end_line=0,
        content=description,
        stage=Stage.PROJECT_SETUP,
        chunk_id=f'project-setup-{index}'
      )
    )
  return tasks


def _test_tasks(files: Iterable[Path], direction: str) -> List[ChunkWorkItem]:
  tasks: List[ChunkWorkItem] = []
  for file_path in files:
    if any(hint.lower() in file_path.name.lower() for hint in TEST_HINTS):
      language = LANGUAGE_EXTENSIONS.get(file_path.suffix.lower(), 'test')
      tasks.append(
        ChunkWorkItem(
          file_path=file_path,
          language=language,
          start_line=1,
          end_line=0,
          content='',
          stage=Stage.TESTS,
          chunk_id=_chunk_id(file_path, 0)
        )
      )
  return tasks
