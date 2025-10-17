from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional


@dataclass
class BatchRequest:
  session_id: str
  project_path: str
  target_path: str
  direction: str
  status: str = 'queued'
  notes: List[str] = field(default_factory=list)


class BatchQueue:
  """In-memory queue for sequential, resumable conversions."""

  def __init__(self) -> None:
    self._queue: Deque[BatchRequest] = deque()
    self._lock = asyncio.Lock()

  async def enqueue(self, request: BatchRequest) -> None:
    async with self._lock:
      self._queue.append(request)

  async def list(self) -> List[BatchRequest]:
    async with self._lock:
      return list(self._queue)

  async def update_status(self, session_id: str, status: str, note: Optional[str] = None) -> None:
    async with self._lock:
      for item in self._queue:
        if item.session_id == session_id:
          item.status = status
          if note:
            item.notes.append(note)
          break

  async def pop_next(self) -> Optional[BatchRequest]:
    async with self._lock:
      if not self._queue:
        return None
      request = self._queue.popleft()
      request.status = 'running'
      return request
