from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass
class BatchItem:
  project_path: Path
  target_path: Path
  direction: str


class BatchManager:
  def __init__(self) -> None:
    self.queue: List[BatchItem] = []

  def schedule(self, projects: List[BatchItem]) -> None:
    self.queue.extend(projects)

  def next_item(self) -> BatchItem | None:
    if not self.queue:
      return None
    return self.queue.pop(0)
