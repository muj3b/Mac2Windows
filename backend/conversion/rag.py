from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from backend.conversion.models import ChunkWorkItem
from backend.storage.embeddings import EmbeddingStore


def _hash_text(text: str) -> str:
  digest = hashlib.sha256(text.encode('utf-8', errors='ignore')).hexdigest()
  return digest[:16]


@dataclass
class RagContextBuilder:
  embedding_store: EmbeddingStore
  collection_name: str = 'conversion-context'
  _in_memory_fallback: Dict[str, Dict[str, str]] = field(default_factory=dict)

  def _collection(self):
    if not self.embedding_store.ready():
      return None
    return self.embedding_store.ensure_collection(self.collection_name)

  def index_project(self, project_root: Path) -> None:
    documents = []
    metadatas = []
    ids = []
    for file_path in project_root.rglob('*'):
      if not file_path.is_file():
        continue
      try:
        text = file_path.read_text(encoding='utf-8')
      except (OSError, UnicodeDecodeError):
        continue
      snippet = text[:4000]
      identifier = _hash_text(str(file_path))
      documents.append(snippet)
      metadatas.append({'file_path': str(file_path), 'stage': 'reference', 'summary': snippet[:256]})
      ids.append(identifier)

    if not documents:
      return

    collection = self._collection()
    if collection:
      collection.upsert(ids=ids, metadatas=metadatas, documents=documents)
    else:
      for identifier, metadata, document in zip(ids, metadatas, documents):
        self._in_memory_fallback[identifier] = {
          'metadata': metadata,
          'document': document
        }

  def register_chunk(self, chunk: ChunkWorkItem, summary: str, converted_text: str) -> None:
    identifier = chunk.chunk_id
    metadata = {
      'file_path': str(chunk.file_path),
      'stage': chunk.stage.name,
      'language': chunk.language,
      'summary': summary
    }
    document = f'{summary}\n\n{converted_text}'
    collection = self._collection()
    if collection:
      collection.upsert(
        ids=[identifier],
        metadatas=[metadata],
        documents=[document]
      )
    else:
      self._in_memory_fallback[identifier] = {
        'metadata': metadata,
        'document': document
      }

  def query_context(self, chunk: ChunkWorkItem, top_k: int = 5) -> List[Dict[str, str]]:
    query_text = '\n'.join(chunk.symbols) if chunk.symbols else chunk.content[:512]
    if not query_text.strip():
      return []

    collection = self._collection()
    if collection:
      response = collection.query(
        query_texts=[query_text],
        n_results=top_k
      )
      results: List[Dict[str, str]] = []
      ids = response.get('ids', [[]])[0]
      metadatas = response.get('metadatas', [[]])[0]
      documents = response.get('documents', [[]])[0]
      for identifier, metadata, document in zip(ids, metadatas, documents):
        if identifier == chunk.chunk_id:
          continue
        results.append(
          {
            'id': identifier,
            'summary': metadata.get('summary', ''),
            'document': document,
            'file_path': metadata.get('file_path', ''),
            'stage': metadata.get('stage', '')
          }
        )
      return results

    scores: List[Tuple[str, int]] = []
    query_tokens = set(query_text.lower().split())
    for identifier, payload in self._in_memory_fallback.items():
      tokens = set(payload['document'].lower().split())
      overlap = len(query_tokens & tokens)
      if overlap:
        scores.append((identifier, overlap))
    scores.sort(key=lambda item: item[1], reverse=True)
    results = []
    for identifier, _ in scores[:top_k]:
      payload = self._in_memory_fallback[identifier]
      metadata = payload['metadata']
      results.append(
        {
          'id': identifier,
          'summary': metadata.get('summary', ''),
          'document': payload['document'],
          'file_path': metadata.get('file_path', ''),
          'stage': metadata.get('stage', '')
        }
      )
    return results
