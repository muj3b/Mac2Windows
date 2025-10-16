from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable


def calculate_checksum(path: Path) -> str:
  data = path.read_bytes()
  return hashlib.sha256(data).hexdigest()


@dataclass
class IncrementalState:
  checksums: Dict[str, str] = field(default_factory=dict)

  def save(self, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as handle:
      json.dump(self.checksums, handle, indent=2)

  @classmethod
  def load(cls, path: Path) -> 'IncrementalState':
    if not path.exists():
      return cls()
    try:
      data = json.loads(path.read_text(encoding='utf-8'))
      if isinstance(data, dict):
        return cls(checksums=data)
    except json.JSONDecodeError:
      pass
    return cls()

  def is_changed(self, file_path: Path, new_checksum: str) -> bool:
    old_checksum = self.checksums.get(str(file_path))
    return old_checksum != new_checksum

  def update_checksum(self, file_path: Path, checksum: str) -> None:
    self.checksums[str(file_path)] = checksum

  def prune_missing(self, existing_paths: Iterable[Path]) -> None:
    existing = {str(path) for path in existing_paths}
    to_remove = [key for key in self.checksums if key not in existing]
    for key in to_remove:
      del self.checksums[key]
