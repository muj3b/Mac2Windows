from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Dict, Any

from backend.conversion.models import ConversionSettings, PerformanceSettings, AISettings


class TemplateManager:
  def __init__(self, base_dir: Path) -> None:
    self.base_dir = base_dir
    self.base_dir.mkdir(parents=True, exist_ok=True)

  def save_template(
    self,
    name: str,
    conversion: ConversionSettings,
    performance: PerformanceSettings,
    ai: AISettings
  ) -> Path:
    path = self.base_dir / f'{name}.json'
    payload = {
      'conversion': asdict(conversion),
      'performance': asdict(performance),
      'ai': asdict(ai)
    }
    path.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    return path

  def load_template(self, name: str) -> Dict[str, Any]:
    path = self.base_dir / f'{name}.json'
    if not path.exists():
      raise FileNotFoundError(name)
    return json.loads(path.read_text(encoding='utf-8'))

  def list_templates(self) -> Dict[str, Any]:
    templates = []
    for path in self.base_dir.glob('*.json'):
      templates.append(path.stem)
    return {'templates': templates}
