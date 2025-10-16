from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from backend.conversion.models import ChunkRecord, ChunkStatus


class ManualImplementationStore:
    def __init__(self, base_path: Path) -> None:
        self.base_path = base_path
        self.base_path.mkdir(parents=True, exist_ok=True)

    def save_implementation(self, chunk_id: str, code: str) -> Path:
        file_path = self.base_path / f"{chunk_id}.manual"
        file_path.write_text(code, encoding='utf-8')
        return file_path

    def list_pending(self) -> List[str]:
        return [file.stem for file in self.base_path.glob('*.manual')]

    def load(self, chunk_id: str) -> str:
        file_path = self.base_path / f"{chunk_id}.manual"
        return file_path.read_text(encoding='utf-8')
