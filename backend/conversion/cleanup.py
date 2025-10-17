from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Iterable, List, Tuple

from backend.conversion.models import CleanupReport, ConversionSettings

logger = logging.getLogger(__name__)

ASSET_EXTENSIONS = {
  '.png',
  '.jpg',
  '.jpeg',
  '.gif',
  '.svg',
  '.pdf',
  '.mp4',
  '.mov',
  '.wav',
  '.mp3'
}

CODE_EXTENSIONS = {'.cs', '.swift', '.m', '.mm', '.cpp', '.h', '.hpp', '.xaml', '.xml', '.json', '.storyboard'}


class CleanupAnalyzer:
  """Identify unused assets & dependencies after conversion."""

  def __init__(self) -> None:
    self._reference_pattern = re.compile(r'([A-Za-z0-9_\-]+\.[A-Za-z0-9]+)')

  def analyze(self, target_root: Path, settings: ConversionSettings) -> CleanupReport:
    report = CleanupReport()
    if not settings.cleanup_unused_assets:
      return report

    assets = self._gather_assets(target_root)
    report.scanned_assets = len(assets)
    if not assets:
      return report

    references = self._collect_references(target_root)
    unused_assets: List[Path] = []
    total_reclaimed = 0

    for asset in assets:
      if asset.name not in references and asset.stem not in references:
        unused_assets.append(asset)
        try:
          total_reclaimed += asset.stat().st_size
        except OSError:
          continue

    report.unused_assets = [str(path.relative_to(target_root)) for path in unused_assets]
    report.total_bytes_reclaimed = total_reclaimed

    dependencies, unused_dependencies = self._scan_dependencies(target_root, references)
    report.scanned_dependencies = len(dependencies)
    report.unused_dependencies = unused_dependencies

    if settings.cleanup_auto_delete:
      auto_deleted = self._delete_unused(unused_assets, target_root, settings.cleanup_min_bytes)
      report.auto_deleted = auto_deleted

    return report

  def _gather_assets(self, root: Path) -> List[Path]:
    assets: List[Path] = []
    for path in root.rglob('*'):
      if not path.is_file():
        continue
      if path.suffix.lower() in ASSET_EXTENSIONS:
        assets.append(path)
    return assets

  def _collect_references(self, root: Path) -> List[str]:
    references: List[str] = []
    for path in root.rglob('*'):
      if not path.is_file():
        continue
      if path.suffix.lower() not in CODE_EXTENSIONS:
        continue
      try:
        text = path.read_text(encoding='utf-8', errors='ignore')
      except (UnicodeDecodeError, OSError):
        continue
      matches = self._reference_pattern.findall(text)
      references.extend(matches)
    return list({ref for ref in references})

  def _scan_dependencies(self, root: Path, references: Iterable[str]) -> Tuple[List[str], List[str]]:
    dependencies: List[str] = []
    unused: List[str] = []
    packages_config = root.rglob('packages.config')
    for path in packages_config:
      try:
        text = path.read_text(encoding='utf-8')
      except OSError:
        continue
      matches = re.findall(r'id="([^"]+)"', text)
      for match in matches:
        dependencies.append(match)
        if not any(match.lower() in ref.lower() for ref in references):
          unused.append(match)
    return dependencies, unused

  def _delete_unused(self, unused_assets: List[Path], root: Path, min_bytes: int) -> List[str]:
    removed: List[str] = []
    for asset in unused_assets:
      try:
        size = asset.stat().st_size
      except OSError:
        continue
      if size < max(min_bytes, 0):
        continue
      try:
        asset.unlink()
        removed.append(str(asset.relative_to(root)))
      except OSError as exc:
        logger.warning('Failed to delete unused asset %s: %s', asset, exc)
    return removed
