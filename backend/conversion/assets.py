from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PIL import Image

logger = logging.getLogger(__name__)


@dataclass
class AssetOptimizationResult:
  original_size: int
  optimized_size: int
  path: Path

  @property
  def savings_bytes(self) -> int:
    return self.original_size - self.optimized_size

  @property
  def savings_percent(self) -> float:
    if self.original_size == 0:
      return 0.0
    return max(0.0, (self.savings_bytes / self.original_size) * 100)


class AssetOptimizer:
  def __init__(self, image_quality: int = 85, max_megapixels: float = 4.0) -> None:
    self.image_quality = max(10, min(image_quality, 100))
    self.max_megapixels = max_megapixels

  def optimize(self, path: Path) -> Optional[AssetOptimizationResult]:
    if path.suffix.lower() not in {'.png', '.jpg', '.jpeg'}:
      return None
    if not path.exists():
      return None

    try:
      original_size = path.stat().st_size
      with Image.open(path) as img:
        pixels = img.width * img.height
        max_pixels = self.max_megapixels * 1_000_000
        if pixels > max_pixels:
          scale = (max_pixels / pixels) ** 0.5
          new_size = (max(1, int(img.width * scale)), max(1, int(img.height * scale)))
          img = img.resize(new_size, Image.LANCZOS)

        if path.suffix.lower() == '.png':
          img.save(path, optimize=True)
        else:
          img = img.convert('RGB')
          img.save(path, quality=self.image_quality, optimize=True)

      optimized_size = path.stat().st_size
      if optimized_size > original_size:
        path.write_bytes(path.read_bytes())  # revert to original if bigger
        optimized_size = original_size
      return AssetOptimizationResult(original_size=original_size, optimized_size=optimized_size, path=path)
    except Exception as exc:
      logger.debug('Asset optimization failed for %s: %s', path, exc)
      return None

  def optimize_directory(self, root: Path) -> list[AssetOptimizationResult]:
    results: list[AssetOptimizationResult] = []
    if not root.exists():
      return results
    for path in root.rglob('*'):
      if path.is_file():
        result = self.optimize(path)
        if result and result.savings_bytes > 0:
          results.append(result)
    return results
