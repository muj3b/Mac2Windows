from __future__ import annotations

import json
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class TemplateDescriptor:
  name: str
  description: str
  owner: str
  tags: List[str]
  created_at: float
  updated_at: float
  path: Path

  def to_dict(self) -> Dict[str, object]:
    payload = asdict(self)
    payload['path'] = str(self.path)
    return payload


class TemplateRepository:
  """Stores metadata for templates to enable sharing/export."""

  def __init__(self, index_path: Path) -> None:
    self.index_path = index_path
    self.index_path.parent.mkdir(parents=True, exist_ok=True)
    if not self.index_path.exists():
      self.index_path.write_text(json.dumps({'templates': []}, indent=2), encoding='utf-8')

  def list(self) -> List[TemplateDescriptor]:
    data = json.loads(self.index_path.read_text(encoding='utf-8'))
    templates: List[TemplateDescriptor] = []
    for entry in data.get('templates', []):
      templates.append(
        TemplateDescriptor(
          name=entry['name'],
          description=entry.get('description', ''),
          owner=entry.get('owner', 'anonymous'),
          tags=entry.get('tags', []),
          created_at=entry.get('created_at', time.time()),
          updated_at=entry.get('updated_at', time.time()),
          path=Path(entry['path'])
        )
      )
    return templates

  def upsert(self, descriptor: TemplateDescriptor) -> None:
    data = {'templates': []}
    if self.index_path.exists():
      data = json.loads(self.index_path.read_text(encoding='utf-8'))
    templates = data.get('templates', [])
    templates = [entry for entry in templates if entry['name'] != descriptor.name]
    templates.append(descriptor.to_dict())
    data['templates'] = templates
    self.index_path.write_text(json.dumps(data, indent=2), encoding='utf-8')

  def get(self, name: str) -> Optional[TemplateDescriptor]:
    for descriptor in self.list():
      if descriptor.name == name:
        return descriptor
    return None

  def remove(self, name: str) -> None:
    if not self.index_path.exists():
      return
    data = json.loads(self.index_path.read_text(encoding='utf-8'))
    templates = [entry for entry in data.get('templates', []) if entry['name'] != name]
    data['templates'] = templates
    self.index_path.write_text(json.dumps(data, indent=2), encoding='utf-8')
