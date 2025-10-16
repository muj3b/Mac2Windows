from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional


class StateStore:
  """SQLite-backed persistence for detection summaries and run metadata."""

  def __init__(self, db_path: Path) -> None:
    self.db_path = Path(db_path)
    self.db_path.parent.mkdir(parents=True, exist_ok=True)
    self._init_schema()

  def _connect(self) -> sqlite3.Connection:
    connection = sqlite3.connect(self.db_path)
    connection.row_factory = sqlite3.Row
    return connection

  def _init_schema(self) -> None:
    with self._connect() as conn:
      conn.execute(
        """
        CREATE TABLE IF NOT EXISTS project_scans (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          project_path TEXT NOT NULL,
          direction TEXT NOT NULL,
          summary_json TEXT NOT NULL,
          analysis_json TEXT NOT NULL,
          metadata_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        """
      )
      conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_project_scans_path ON project_scans(project_path);"
      )
      conn.commit()

  def record_scan(self, result: Dict[str, Any]) -> None:
    timestamp = datetime.now(timezone.utc).isoformat()
    payload = {
      'project_path': result['project_path'],
      'direction': result.get('direction', 'mac-to-win'),
      'summary_json': json.dumps(result.get('summary', {})),
      'analysis_json': json.dumps(result.get('analysis', {})),
      'metadata_json': json.dumps(
        {
          'languages': result.get('languages', []),
          'frameworks': result.get('frameworks', {}),
          'dependencies': result.get('dependencies', []),
          'build_configs': result.get('build_configs', []),
          'mixed_languages': result.get('mixed_languages', False),
          'suggested_targets': result.get('suggested_targets', [])
        }
      ),
      'created_at': timestamp
    }
    with self._connect() as conn:
      conn.execute(
        """
        INSERT INTO project_scans (
          project_path, direction, summary_json, analysis_json, metadata_json, created_at
        ) VALUES (:project_path, :direction, :summary_json, :analysis_json, :metadata_json, :created_at)
        """,
        payload
      )
      conn.commit()

  def latest_scans(self, limit: int = 5) -> Iterable[Dict[str, Any]]:
    with self._connect() as conn:
      rows = conn.execute(
        """
        SELECT project_path, direction, summary_json, analysis_json, metadata_json, created_at
        FROM project_scans
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (limit,)
      ).fetchall()
      for row in rows:
        yield {
          'project_path': row['project_path'],
          'direction': row['direction'],
          'summary': json.loads(row['summary_json']),
          'analysis': json.loads(row['analysis_json']),
          'metadata': json.loads(row['metadata_json']),
          'created_at': row['created_at']
        }
