from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

try:
  import chromadb  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
  chromadb = None


class EmbeddingStore:
  """Thin wrapper around ChromaDB. Falls back gracefully if dependency missing."""

  def __init__(self, storage_path: Path) -> None:
    self.storage_path = Path(storage_path)
    self.storage_path.mkdir(parents=True, exist_ok=True)
    self._client = self._init_client()

  def _init_client(self):
    if chromadb is None:
      return None
    return chromadb.PersistentClient(path=str(self.storage_path))

  def ready(self) -> bool:
    return self._client is not None

  def basic_status(self) -> Dict[str, Any]:
    return {
      'enabled': self.ready(),
      'storage_path': str(self.storage_path),
      'client': self._client.__class__.__name__ if self._client else None
    }

  def ensure_collection(self, name: str):
    if not self._client:
      return None
    try:
      return self._client.get_or_create_collection(name=name)
    except Exception as error:  # pragma: no cover - defensive
      raise RuntimeError(f'Failed to access ChromaDB collection {name}') from error
