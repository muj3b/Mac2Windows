from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, Optional

from backend.conversion.models import (
  ChunkRecord,
  ConversionSummary,
  Stage,
  StageProgress,
  STAGE_ORDER,
  STAGE_WEIGHTS
)


@dataclass
class ProgressTracker:
  direction: str
  stage_progress: Dict[Stage, StageProgress] = field(default_factory=dict)
  started_at: float = field(default_factory=time.time)
  updated_at: float = field(default_factory=time.time)
  total_tokens: int = 0
  total_cost_usd: float = 0.0
  total_chunks: int = 0
  completed_chunks: int = 0
  paused: bool = False
  last_chunk: Optional[ChunkRecord] = None

  def ensure_stage(self, stage: Stage, total_units: int) -> StageProgress:
    if stage not in self.stage_progress:
      self.stage_progress[stage] = StageProgress(stage=stage, total_units=total_units)
    else:
      self.stage_progress[stage].total_units = total_units
    return self.stage_progress[stage]

  def start_stage(self, stage: Stage) -> None:
    progress = self.stage_progress[stage]
    progress.status = 'running'
    self.updated_at = time.time()

  def complete_stage(self, stage: Stage) -> None:
    progress = self.stage_progress[stage]
    progress.status = 'completed'
    progress.completed_units = progress.total_units
    self.updated_at = time.time()

  def pause(self) -> None:
    self.paused = True
    self._set_running_stages_status('paused')
    self.updated_at = time.time()

  def resume(self) -> None:
    self.paused = False
    self._set_running_stages_status('running', resume=True)
    self.updated_at = time.time()

  def _set_running_stages_status(self, status: str, resume: bool = False) -> None:
    for progress in self.stage_progress.values():
      if resume and progress.status == 'paused':
        progress.status = 'running'
      elif progress.status == 'running':
        progress.status = status

  def register_chunk(self, chunk: ChunkRecord) -> None:
    progress = self.stage_progress.get(chunk.chunk.stage)
    if progress:
      self.total_chunks += 1

  def update_chunk(self, chunk: ChunkRecord) -> None:
    progress = self.stage_progress.get(chunk.chunk.stage)
    if not progress:
      return
    if chunk.status.name.lower() == 'completed':
      progress.completed_units += 1
      self.completed_chunks += 1
    self.total_tokens += chunk.tokens_used
    self.total_cost_usd += chunk.cost_usd
    self.updated_at = time.time()
    self.last_chunk = chunk

  def summary(self) -> ConversionSummary:
    elapsed = time.time() - self.started_at
    remaining_percentage = max(0.0, 1.0 - self._overall_percentage())
    est_seconds = (elapsed / max(self._overall_percentage(), 0.01)) * remaining_percentage if self.completed_chunks else None
    return ConversionSummary(
      total_files=self.total_chunks,
      converted_files=self.completed_chunks,
      elapsed_seconds=elapsed,
      estimated_seconds_remaining=est_seconds,
      tokens_used=self.total_tokens,
      cost_usd=round(self.total_cost_usd, 4),
      stage_progress=self.stage_progress,
      current_chunk=self.last_chunk,
      overall_percentage=self._overall_percentage(),
      paused=self.paused,
      direction=self.direction
    )

  def _overall_percentage(self) -> float:
    total = 0.0
    for stage in STAGE_ORDER:
      progress = self.stage_progress.get(stage)
      if not progress:
        continue
      total += STAGE_WEIGHTS[stage] * progress.percentage
    return min(1.0, total)
