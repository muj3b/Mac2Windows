from __future__ import annotations

import json
import plistlib
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import psutil


UI_EXTENSIONS_MAC = ('.storyboard', '.xib', '.swiftui')
UI_EXTENSIONS_WIN = ('.xaml', '.cshtml', '.razor')
DATA_EXTENSIONS = ('.json', '.plist', '.resx', '.xml')


@dataclass
class BenchmarkMetric:
  duration: float
  cpu_seconds: float
  memory_delta: int
  details: Dict[str, Any]


def run_benchmarks(
  original_project: Path,
  converted_project: Path,
  direction: str,
  regression_threshold: float = 0.20
) -> Dict[str, Any]:
  direction = direction.lower()
  if direction == 'mac-to-win':
    original_metrics = _collect_metrics(original_project, UI_EXTENSIONS_MAC)
    converted_metrics = _collect_metrics(converted_project, UI_EXTENSIONS_WIN)
  else:
    original_metrics = _collect_metrics(original_project, UI_EXTENSIONS_WIN)
    converted_metrics = _collect_metrics(converted_project, UI_EXTENSIONS_MAC)

  comparisons, regressions = _compare_metrics(original_metrics, converted_metrics, regression_threshold)
  return {
    'original': original_metrics,
    'converted': converted_metrics,
    'comparisons': comparisons,
    'regressions': regressions,
    'threshold': regression_threshold
  }


def _collect_metrics(project_root: Path, ui_extensions: Tuple[str, ...]) -> Dict[str, Any]:
  project_root = Path(project_root)
  metrics: Dict[str, Any] = {
    'project': str(project_root),
    'file_stats': _file_statistics(project_root)
  }
  ui_file = _find_first(project_root, ui_extensions)
  data_file = _find_first(project_root, DATA_EXTENSIONS)
  metrics['ui'] = _measure_ui(ui_file) if ui_file else None
  metrics['data'] = _measure_data(data_file) if data_file else None
  return metrics


def _file_statistics(project_root: Path) -> Dict[str, Any]:
  total_files = 0
  total_lines = 0
  total_size = 0
  for file_path in project_root.rglob('*'):
    if not file_path.is_file():
      continue
    total_files += 1
    try:
      text = file_path.read_text(encoding='utf-8', errors='ignore')
      total_lines += len(text.splitlines())
    except OSError:
      pass
    try:
      total_size += file_path.stat().st_size
    except OSError:
      continue
  return {
    'total_files': total_files,
    'total_lines': total_lines,
    'total_size_bytes': total_size
  }


def _find_first(project_root: Path, extensions: Tuple[str, ...]) -> Optional[Path]:
  for ext in extensions:
    candidate = next(project_root.rglob(f'*{ext}'), None)
    if candidate:
      return candidate
  return None


def _measure_ui(ui_path: Optional[Path]) -> Optional[Dict[str, Any]]:
  if not ui_path:
    return None
  metric = _measure_operation(lambda: _parse_ui(ui_path))
  return {
    'file': str(ui_path),
    'duration': metric.duration,
    'cpu_seconds': metric.cpu_seconds,
    'memory_delta': metric.memory_delta,
    'details': metric.details
  }


def _measure_data(data_path: Optional[Path]) -> Optional[Dict[str, Any]]:
  if not data_path:
    return None
  metric = _measure_operation(lambda: _parse_data(data_path))
  return {
    'file': str(data_path),
    'duration': metric.duration,
    'cpu_seconds': metric.cpu_seconds,
    'memory_delta': metric.memory_delta,
    'details': metric.details
  }


def _measure_operation(callback) -> BenchmarkMetric:
  process = psutil.Process()
  start_cpu = process.cpu_times()
  start_mem = process.memory_info().rss
  start = time.perf_counter()
  details = callback()
  duration = time.perf_counter() - start
  end_cpu = process.cpu_times()
  end_mem = process.memory_info().rss
  cpu_seconds = (end_cpu.user - start_cpu.user) + (end_cpu.system - start_cpu.system)
  memory_delta = end_mem - start_mem
  return BenchmarkMetric(duration=duration, cpu_seconds=cpu_seconds, memory_delta=memory_delta, details=details)


def _parse_ui(ui_path: Path) -> Dict[str, Any]:
  suffix = ui_path.suffix.lower()
  if suffix in {'.storyboard', '.xib', '.xaml', '.resx'}:
    tree = ET.parse(ui_path)
    element_count = sum(1 for _ in tree.iter())
    return {'elements': element_count}
  text = ui_path.read_text(encoding='utf-8', errors='ignore')
  return {'lines': len(text.splitlines())}


def _parse_data(data_path: Path) -> Dict[str, Any]:
  suffix = data_path.suffix.lower()
  if suffix == '.json':
    payload = json.loads(data_path.read_text(encoding='utf-8', errors='ignore') or '{}')
    size = len(payload if isinstance(payload, dict) else [])
    return {'entries': size}
  if suffix == '.plist':
    with data_path.open('rb') as handle:
      payload = plistlib.load(handle)
    size = len(payload) if isinstance(payload, dict) else len(payload or [])
    return {'entries': size}
  if suffix in {'.xml', '.resx'}:
    tree = ET.parse(data_path)
    element_count = sum(1 for _ in tree.iter())
    return {'elements': element_count}
  text = data_path.read_text(encoding='utf-8', errors='ignore')
  return {'lines': len(text.splitlines())}


def _compare_metrics(
  original: Dict[str, Any],
  converted: Dict[str, Any],
  threshold: float
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
  comparisons: List[Dict[str, Any]] = []
  regressions: List[Dict[str, Any]] = []

  for label in ('ui', 'data'):
    orig_metric = original.get(label)
    conv_metric = converted.get(label)
    if not orig_metric or not conv_metric:
      continue
    comparison = _build_comparison(label, orig_metric, conv_metric, threshold)
    comparisons.append(comparison)
    if comparison['regression']:
      regressions.append(comparison)

  return comparisons, regressions


def _build_comparison(label: str, original: Dict[str, Any], converted: Dict[str, Any], threshold: float) -> Dict[str, Any]:
  baseline = original.get('duration') or 0.0
  candidate = converted.get('duration') or 0.0
  if baseline == 0:
    delta_pct = 0.0 if candidate == 0 else 1.0
  else:
    delta_pct = (candidate - baseline) / baseline
  regression = delta_pct > threshold
  return {
    'metric': label,
    'original_duration': baseline,
    'converted_duration': candidate,
    'delta_pct': delta_pct,
    'regression': regression,
    'original_memory_delta': original.get('memory_delta'),
    'converted_memory_delta': converted.get('memory_delta'),
    'original_cpu_seconds': original.get('cpu_seconds'),
    'converted_cpu_seconds': converted.get('cpu_seconds')
  }
