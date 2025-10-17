from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


class LearningMemory:
  THRESHOLD = 3

  def __init__(self, storage_path: Path) -> None:
    self.storage_path = storage_path
    self.storage_path.parent.mkdir(parents=True, exist_ok=True)
    if not self.storage_path.exists():
      self.storage_path.write_text(json.dumps({'patterns': []}), encoding='utf-8')

  # Legacy support for previous API
  def record(self, issue: str, correction: str) -> None:  # pragma: no cover - legacy hook
    self.record_manual_fix(issue, correction, metadata={'legacy': True})

  def record_manual_fix(self, original: str, corrected: str, metadata: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    if not original or not corrected:
      return None
    metadata = metadata or {}
    data = self._load()
    fp = self.fingerprint(original)
    pattern = self._find_pattern(data, fp)
    threshold_override = metadata.get('threshold')
    threshold_value: Optional[int] = None
    if isinstance(threshold_override, int) and threshold_override > 0:
      threshold_value = max(1, threshold_override)
    if not pattern:
      effective_threshold = threshold_value or self.THRESHOLD
      pattern = {
        'fingerprint': fp,
        'original_example': original,
        'replacement': corrected,
        'count': 0,
        'auto_attempts': 0,
        'auto_successes': 0,
        'auto_failures': 0,
        'threshold': effective_threshold,
        'metadata': [],
        'hint': metadata.get('note') or metadata.get('reason'),
        'created_at': time.time()
      }
      data['patterns'].append(pattern)
    else:
      if threshold_value:
        pattern['threshold'] = threshold_value
    pattern.setdefault('metadata', [])

    pattern['count'] += 1
    pattern['replacement'] = corrected
    pattern['original_example'] = original
    if metadata.get('note'):
      pattern['hint'] = metadata['note']
    pattern['metadata'].append({**metadata, 'timestamp': time.time(), 'type': 'manual_fix'})
    self._save(data)
    return pattern

  def get_pattern(self, content: str) -> Optional[Dict[str, Any]]:
    if not content:
      return None
    data = self._load()
    fp = self.fingerprint(content)
    pattern = self._find_pattern(data, fp)
    if not pattern:
      return None
    if pattern['count'] < pattern.get('threshold', self.THRESHOLD):
      return None
    return {**pattern}

  def register_auto_attempt(self, fingerprint: str, metadata: Optional[Dict[str, Any]] = None) -> None:
    data = self._load()
    pattern = self._find_pattern(data, fingerprint)
    if not pattern:
      return
    pattern['auto_attempts'] = pattern.get('auto_attempts', 0) + 1
    pattern.setdefault('applications', []).append({**(metadata or {}), 'timestamp': time.time(), 'type': 'auto_attempt'})
    self._save(data)

  def mark_auto_success(self, fingerprint: str, success: bool) -> None:
    data = self._load()
    pattern = self._find_pattern(data, fingerprint)
    if not pattern:
      return
    key = 'auto_successes' if success else 'auto_failures'
    pattern[key] = pattern.get(key, 0) + 1
    self._save(data)

  def suggestions(self, content: str) -> Dict[str, Any]:
    pattern = self.get_pattern(content)
    if not pattern:
      return {'matches': []}
    hint = pattern.get('hint') or 'Apply previously learned correction pattern.'
    success = pattern.get('auto_successes', 0)
    attempts = pattern.get('auto_attempts', 0)
    rate = f"success rate {success}/{attempts}" if attempts else 'not auto-applied yet'
    return {'matches': [f"Learned pattern ({pattern['count']} fixes, {rate}): {hint}"]}

  def list_patterns(self) -> List[Dict[str, Any]]:
    data = self._load()
    patterns = []
    for pattern in data.get('patterns', []):
      attempts = pattern.get('auto_attempts', 0)
      successes = pattern.get('auto_successes', 0)
      failures = pattern.get('auto_failures', 0)
      patterns.append({
        'fingerprint': pattern['fingerprint'],
        'count': pattern.get('count', 0),
        'auto_attempts': attempts,
        'auto_successes': successes,
        'auto_failures': failures,
        'hint': pattern.get('hint'),
        'ready': pattern.get('count', 0) >= pattern.get('threshold', self.THRESHOLD)
      })
    return patterns

  def get_pattern_by_fingerprint(self, fingerprint: str) -> Optional[Dict[str, Any]]:
    data = self._load()
    pattern = self._find_pattern(data, fingerprint)
    if not pattern:
      return None
    return {**pattern}

  def fingerprint(self, content: str) -> str:
    tokens = re.findall(r'[A-Za-z_]+', content or '')
    normalized = ' '.join(tokens[:800]).lower()
    if not normalized:
      normalized = (content or '').strip().lower()[:800]
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()

  def _find_pattern(self, data: Dict[str, Any], fingerprint: str) -> Optional[Dict[str, Any]]:
    for pattern in data.get('patterns', []):
      if pattern.get('fingerprint') == fingerprint:
        return pattern
    return None

  def _load(self) -> Dict[str, Any]:
    try:
      return json.loads(self.storage_path.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
      return {'patterns': []}

  def _save(self, data: Dict[str, Any]) -> None:
    self.storage_path.write_text(json.dumps(data, indent=2), encoding='utf-8')
