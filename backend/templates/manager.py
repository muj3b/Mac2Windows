from __future__ import annotations

import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.conversion.models import ConversionSettings, PerformanceSettings, AISettings
from backend.storage.templates import TemplateRepository, TemplateDescriptor


class TemplateManager:
  def __init__(self, base_dir: Path, repository: Optional[TemplateRepository] = None) -> None:
    self.base_dir = base_dir
    self.base_dir.mkdir(parents=True, exist_ok=True)
    self.repository = repository or TemplateRepository(self.base_dir / 'templates_index.json')

  def save_template(
    self,
    name: str,
    conversion: ConversionSettings,
    performance: PerformanceSettings,
    ai: AISettings,
    description: str = '',
    owner: str = 'local',
    tags: Optional[List[str]] = None
  ) -> Path:
    path = self.base_dir / f'{name}.json'
    payload = {
      'conversion': asdict(conversion),
      'performance': asdict(performance),
      'ai': asdict(ai)
    }
    path.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    descriptor = TemplateDescriptor(
      name=name,
      description=description,
      owner=owner,
      tags=tags or [],
      created_at=time.time(),
      updated_at=time.time(),
      path=path
    )
    self.repository.upsert(descriptor)
    return path

  def load_template(self, name: str) -> Dict[str, Any]:
    path = self.base_dir / f'{name}.json'
    if not path.exists():
      raise FileNotFoundError(name)
    return json.loads(path.read_text(encoding='utf-8'))

  def list_templates(self) -> Dict[str, Any]:
    descriptors = [descriptor.to_dict() for descriptor in self.repository.list()]
    return {'templates': descriptors}

  def delete_template(self, name: str) -> None:
    path = self.base_dir / f'{name}.json'
    if path.exists():
      path.unlink()
    self.repository.remove(name)

  def share_template(self, name: str, description: str, owner: str, tags: Optional[List[str]] = None) -> Dict[str, Any]:
    descriptor = self.repository.get(name)
    if not descriptor:
      raise FileNotFoundError(name)
    descriptor.description = description
    descriptor.owner = owner
    descriptor.tags = tags or []
    descriptor.updated_at = time.time()
    self.repository.upsert(descriptor)
    return descriptor.to_dict()
