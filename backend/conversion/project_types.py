from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class ProjectProfile:
  project_type: str
  confidence: float
  indicators: Dict[str, int]


class ProjectTypeDetector:
  """Detects project archetypes to tailor conversion prompts."""

  TYPE_HINTS = {
    'game': {'SpriteKit', 'SceneKit', 'GameplayKit', 'Metal', 'DirectX', 'UnityPlayer'},
    'data': {'CoreData', 'SQL', 'Realm', 'EFCore', 'EntityFramework'},
    'media': {'AVFoundation', 'CoreAudio', 'MediaPlayer', 'MediaKit'},
    'simple': {'UIKit', 'SwiftUI', 'WinUI', 'WPF'},
    'enterprise': {'AppKit', 'SharePoint', 'AzureAD', 'OAuth'}
  }

  def analyse(self, project_path: Path) -> ProjectProfile:
    scores: Dict[str, int] = {key: 0 for key in self.TYPE_HINTS.keys()}
    files_scanned = 0

    for path in project_path.rglob('*'):
      if not path.is_file():
        continue
      if path.suffix.lower() not in {'.swift', '.m', '.mm', '.cs', '.xaml', '.json', '.plist'}:
        continue
      try:
        text = path.read_text(encoding='utf-8', errors='ignore')
      except OSError:
        continue
      files_scanned += 1
      for project_type, hints in self.TYPE_HINTS.items():
        matches = sum(1 for hint in hints if hint in text)
        scores[project_type] += matches

    if files_scanned == 0:
      return ProjectProfile(project_type='simple', confidence=0.2, indicators=scores)

    detected_type = max(scores.items(), key=lambda item: item[1])[0]
    max_score = scores[detected_type]
    confidence = min(max_score / max(files_scanned, 1), 1.0)
    if max_score == 0:
      detected_type = 'simple'
      confidence = 0.15

    return ProjectProfile(project_type=detected_type, confidence=round(confidence, 2), indicators=scores)
