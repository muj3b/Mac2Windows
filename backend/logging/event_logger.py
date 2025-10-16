from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


class EventLogger:
  def __init__(self, base_dir: Path) -> None:
    self.base_dir = base_dir
    self.base_dir.mkdir(parents=True, exist_ok=True)
    self.log_file = self.base_dir / 'events.log'

  def log_event(self, category: str, message: str, payload: Dict[str, Any] | None = None) -> None:
    entry = {
      'timestamp': datetime.utcnow().isoformat(),
      'category': category,
      'message': message,
      'payload': payload or {}
    }
    with self.log_file.open('a', encoding='utf-8') as handle:
      handle.write(json.dumps(entry) + '\n')

  def log_error(self, message: str, payload: Dict[str, Any] | None = None) -> None:
    self.log_event('error', message, payload)

  def recent(self, limit: int = 200) -> List[Dict[str, Any]]:
    if not self.log_file.exists():
      return []
    lines = self.log_file.read_text(encoding='utf-8').splitlines()[-limit:]
    entries = []
    for line in lines:
      try:
        entries.append(json.loads(line))
      except json.JSONDecodeError:
        logging.warning('Malformed log line: %s', line)
    return entries
