from __future__ import annotations

import json
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from backend.security.secret_manager import SecretManager


@dataclass
class CredentialRecord:
  id: str
  provider: str
  label: str
  data: Dict[str, Any]
  created_at: float
  updated_at: float


@dataclass
class BackupRecord:
  id: str
  session_id: str
  provider: str
  credential_id: Optional[str]
  remote_id: Optional[str]
  remote_url: Optional[str]
  metadata: Dict[str, Any]
  created_at: float


class CredentialStore:
  """SQLite-backed encrypted credential and backup registry."""

  def __init__(self, db_path: Path, secret_manager: SecretManager) -> None:
    self.db_path = Path(db_path)
    self.db_path.parent.mkdir(parents=True, exist_ok=True)
    self.secret_manager = secret_manager
    self._init_schema()

  def _connect(self) -> sqlite3.Connection:
    connection = sqlite3.connect(self.db_path)
    connection.row_factory = sqlite3.Row
    return connection

  def _init_schema(self) -> None:
    with self._connect() as conn:
      conn.execute(
        """
        CREATE TABLE IF NOT EXISTS credentials (
          id TEXT PRIMARY KEY,
          provider TEXT NOT NULL,
          label TEXT NOT NULL,
          payload BLOB NOT NULL,
          created_at REAL NOT NULL,
          updated_at REAL NOT NULL
        );
        """
      )
      conn.execute(
        """
        CREATE TABLE IF NOT EXISTS backup_records (
          id TEXT PRIMARY KEY,
          session_id TEXT NOT NULL,
          provider TEXT NOT NULL,
          credential_id TEXT,
          remote_id TEXT,
          remote_url TEXT,
          metadata_json TEXT NOT NULL,
          created_at REAL NOT NULL,
          FOREIGN KEY(credential_id) REFERENCES credentials(id) ON DELETE SET NULL
        );
        """
      )
      conn.execute("CREATE INDEX IF NOT EXISTS idx_credentials_provider ON credentials(provider);")
      conn.execute("CREATE INDEX IF NOT EXISTS idx_backups_provider ON backup_records(provider);")
      conn.execute("CREATE INDEX IF NOT EXISTS idx_backups_session ON backup_records(session_id);")
      conn.commit()

  def save_credentials(self, provider: str, label: str, data: Dict[str, Any]) -> CredentialRecord:
    record_id = uuid.uuid4().hex
    now = time.time()
    payload = self.secret_manager.encrypt(json.dumps(data).encode('utf-8'))
    with self._connect() as conn:
      conn.execute(
        """
        INSERT INTO credentials (id, provider, label, payload, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (record_id, provider, label, payload, now, now)
      )
      conn.commit()
    return CredentialRecord(
      id=record_id,
      provider=provider,
      label=label,
      data=data,
      created_at=now,
      updated_at=now
    )

  def update_credentials(self, credential_id: str, data: Dict[str, Any]) -> Optional[CredentialRecord]:
    now = time.time()
    payload = self.secret_manager.encrypt(json.dumps(data).encode('utf-8'))
    with self._connect() as conn:
      cursor = conn.execute(
        """
        UPDATE credentials
        SET payload = ?, updated_at = ?
        WHERE id = ?
        """,
        (payload, now, credential_id)
      )
      if cursor.rowcount == 0:
        return None
      row = conn.execute(
        "SELECT id, provider, label, payload, created_at, updated_at FROM credentials WHERE id = ?",
        (credential_id,)
      ).fetchone()
      conn.commit()
    if not row:
      return None
    data_payload = json.loads(self.secret_manager.decrypt(row['payload']).decode('utf-8'))
    return CredentialRecord(
      id=row['id'],
      provider=row['provider'],
      label=row['label'],
      data=data_payload,
      created_at=row['created_at'],
      updated_at=row['updated_at']
    )

  def delete_credentials(self, credential_id: str) -> bool:
    with self._connect() as conn:
      cursor = conn.execute("DELETE FROM credentials WHERE id = ?", (credential_id,))
      conn.commit()
    return cursor.rowcount > 0

  def get_credentials(self, credential_id: str) -> Optional[CredentialRecord]:
    with self._connect() as conn:
      row = conn.execute(
        "SELECT id, provider, label, payload, created_at, updated_at FROM credentials WHERE id = ?",
        (credential_id,)
      ).fetchone()
    if not row:
      return None
    data = json.loads(self.secret_manager.decrypt(row['payload']).decode('utf-8'))
    return CredentialRecord(
      id=row['id'],
      provider=row['provider'],
      label=row['label'],
      data=data,
      created_at=row['created_at'],
      updated_at=row['updated_at']
    )

  def list_credentials(self, provider: Optional[str] = None) -> List[CredentialRecord]:
    query = "SELECT id, provider, label, payload, created_at, updated_at FROM credentials"
    params: Sequence[Any] = ()
    if provider:
      query += " WHERE provider = ?"
      params = (provider,)
    query += " ORDER BY created_at DESC"
    with self._connect() as conn:
      rows = conn.execute(query, params).fetchall()
    records: List[CredentialRecord] = []
    for row in rows:
      data = json.loads(self.secret_manager.decrypt(row['payload']).decode('utf-8'))
      records.append(
        CredentialRecord(
          id=row['id'],
          provider=row['provider'],
          label=row['label'],
          data=data,
          created_at=row['created_at'],
          updated_at=row['updated_at']
        )
      )
    return records

  def record_backup(
    self,
    session_id: str,
    provider: str,
    metadata: Dict[str, Any],
    credential_id: Optional[str] = None,
    remote_id: Optional[str] = None,
    remote_url: Optional[str] = None
  ) -> BackupRecord:
    record_id = uuid.uuid4().hex
    now = time.time()
    with self._connect() as conn:
      conn.execute(
        """
        INSERT INTO backup_records (
          id, session_id, provider, credential_id, remote_id, remote_url, metadata_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
          record_id,
          session_id,
          provider,
          credential_id,
          remote_id,
          remote_url,
          json.dumps(metadata),
          now
        )
      )
      conn.commit()
    return BackupRecord(
      id=record_id,
      session_id=session_id,
      provider=provider,
      credential_id=credential_id,
      remote_id=remote_id,
      remote_url=remote_url,
      metadata=metadata,
      created_at=now
    )

  def list_backups(
    self,
    provider: Optional[str] = None,
    credential_id: Optional[str] = None,
    session_id: Optional[str] = None
  ) -> List[BackupRecord]:
    query = "SELECT * FROM backup_records"
    filters: List[str] = []
    params: List[Any] = []
    if provider:
      filters.append("provider = ?")
      params.append(provider)
    if credential_id:
      filters.append("credential_id = ?")
      params.append(credential_id)
    if session_id:
      filters.append("session_id = ?")
      params.append(session_id)
    if filters:
      query += " WHERE " + " AND ".join(filters)
    query += " ORDER BY created_at DESC"
    with self._connect() as conn:
      rows = conn.execute(query, tuple(params)).fetchall()
    records: List[BackupRecord] = []
    for row in rows:
      records.append(
        BackupRecord(
          id=row['id'],
          session_id=row['session_id'],
          provider=row['provider'],
          credential_id=row['credential_id'],
          remote_id=row['remote_id'],
          remote_url=row['remote_url'],
          metadata=json.loads(row['metadata_json']),
          created_at=row['created_at']
        )
      )
    return records

  def delete_backup(self, backup_id: str) -> bool:
    with self._connect() as conn:
      cursor = conn.execute("DELETE FROM backup_records WHERE id = ?", (backup_id,))
      conn.commit()
    return cursor.rowcount > 0
