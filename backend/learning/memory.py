from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any


class LearningMemory:
  def __init__(self, storage_path: Path) -> None:
    self.storage_path = storage_path
    self.storage_path.parent.mkdir(parents=True, exist_ok=True)
    if not self.storage_path.exists():
      self.storage_path.write_text(json.dumps({'patterns': []}), encoding='utf-8')

  def record(self, issue: str, correction: str) -> None:
    data = self._load()
    data['patterns'].append({'issue': issue, 'correction': correction})
    self._save(data)

  def suggestions(self, content: str) -> Dict[str, Any]:
    data = self._load()
    matches = []
    for pattern in data.get('patterns', []):
      if pattern['issue'] in content:
        matches.append(pattern['correction'])
    return {'matches': matches}

  def _load(self) -> Dict[str, Any]:
    try:
      return json.loads(self.storage_path.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
      return {'patterns': []}

  def _save(self, data: Dict[str, Any]) -> None:
    self.storage_path.write_text(json.dumps(data, indent=2), encoding='utf-8')
