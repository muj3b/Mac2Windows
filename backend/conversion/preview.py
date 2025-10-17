from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional, Sequence

from backend.conversion.chunker import generate_work_plan
from backend.conversion.models import PreviewEstimate


@dataclass
class PreviewOptions:
  exclusions: Sequence[str]


class PreviewAnalyzer:
  """Computes dry-run previews without mutating the project."""

  def __init__(self) -> None:
    self.average_tokens_per_chunk = 480
    self.average_seconds_per_chunk = 14

  def analyze(
    self,
    project_path: Path,
    direction: str,
    exclusions: Optional[Iterable[str]] = None
  ) -> PreviewEstimate:
    plan = generate_work_plan(project_path, direction)
    excluded = set(exclusions or [])
    stage_breakdown: Dict[str, Dict[str, float]] = {}
    total_chunks = 0

    for stage, chunks in plan.items():
      filtered = [
        chunk
        for chunk in chunks
        if not any(exclusion in str(chunk.file_path) for exclusion in excluded)
      ]
      chunk_count = len(filtered)
      total_chunks += chunk_count
      stage_breakdown[stage.name] = {
        'chunks': chunk_count,
        'files': len({chunk.file_path for chunk in filtered}),
        'estimated_tokens': chunk_count * self.average_tokens_per_chunk,
        'estimated_minutes': chunk_count * self.average_seconds_per_chunk / 60.0
      }

    estimate = PreviewEstimate()
    estimate.stage_breakdown = stage_breakdown
    estimate.impacted_files = sum(int(entry['files']) for entry in stage_breakdown.values())
    estimate.total_files = estimate.impacted_files
    estimate.estimated_tokens = total_chunks * self.average_tokens_per_chunk
    estimate.estimated_minutes = round(total_chunks * self.average_seconds_per_chunk / 60.0, 2)
    estimate.estimated_cost_usd = round(self._estimate_cost(estimate.estimated_tokens), 2)
    return estimate

  def _estimate_cost(self, tokens: int) -> float:
    price_per_1k = 0.024  # conservative default
    return price_per_1k * (tokens / 1000.0)
