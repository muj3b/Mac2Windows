from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional

from backend.conversion.models import (
  SessionState,
  StageProgress,
  Stage,
  ChunkRecord,
  ChunkStatus,
  STAGE_ORDER,
  QualityReport,
  QualityIssue,
  ConversionReport,
  ConversionSettings,
  PerformanceSettings,
  AISettings
)


def _connect(db_path: Path) -> sqlite3.Connection:
  connection = sqlite3.connect(db_path)
  connection.row_factory = sqlite3.Row
  return connection


class ConversionSessionStore:
  def __init__(self, db_path: Path) -> None:
    self.db_path = Path(db_path)
    self.db_path.parent.mkdir(parents=True, exist_ok=True)
    self._init_schema()

  def _init_schema(self) -> None:
    with _connect(self.db_path) as conn:
      conn.execute(
        """
        CREATE TABLE IF NOT EXISTS conversion_sessions (
          id TEXT PRIMARY KEY,
          project_path TEXT NOT NULL,
          target_path TEXT NOT NULL,
          direction TEXT NOT NULL,
          stage_progress_json TEXT NOT NULL,
          chunks_json TEXT NOT NULL,
          paused INTEGER NOT NULL,
          summary_notes_json TEXT NOT NULL,
          symbol_table_json TEXT NOT NULL,
          quality_report_json TEXT,
          conversion_settings_json TEXT,
          performance_settings_json TEXT,
          ai_settings_json TEXT,
          webhooks_json TEXT,
          conversion_report_json TEXT,
          created_at REAL NOT NULL,
          updated_at REAL NOT NULL
        );
        """
      )
      for column, definition in (
        ('quality_report_json', 'TEXT'),
        ('conversion_settings_json', 'TEXT'),
        ('performance_settings_json', 'TEXT'),
        ('ai_settings_json', 'TEXT'),
        ('webhooks_json', 'TEXT'),
        ('conversion_report_json', 'TEXT')
      ):
        self._ensure_column(conn, column, definition)
      conn.commit()

  def upsert(self, state: SessionState) -> None:
    payload = {
      'id': state.session_id,
      'project_path': str(state.project_path),
      'target_path': str(state.target_path),
      'direction': state.direction,
      'stage_progress_json': json.dumps(
        {
          stage.name: {
            'completed_units': progress.completed_units,
            'total_units': progress.total_units,
            'status': progress.status
          }
          for stage, progress in state.stage_progress.items()
        }
      ),
      'chunks_json': json.dumps(
        {
          chunk_id: {
            'chunk_id': chunk_id,
            'file_path': str(record.chunk.file_path),
            'stage': record.chunk.stage.name,
            'language': record.chunk.language,
            'start_line': record.chunk.start_line,
            'end_line': record.chunk.end_line,
            'status': record.status.name,
            'output_path': str(record.output_path) if record.output_path else None,
            'tokens_used': record.tokens_used,
            'input_tokens': record.input_tokens,
            'output_tokens': record.output_tokens,
            'cost_usd': record.cost_usd,
            'summary': record.summary,
            'last_error': record.last_error,
            'partial_completion': record.partial_completion,
            'ai_model': record.ai_model,
            'provider_id': record.provider_id,
            'raw_output': record.raw_output
          }
          for chunk_id, record in state.chunks.items()
        }
      ),
      'paused': 1 if state.paused else 0,
      'summary_notes_json': json.dumps(state.summary_notes),
      'symbol_table_json': json.dumps(
        {
          identifier: {
            'kind': entry.kind,
            'location': entry.location,
            'metadata': entry.metadata
          }
          for identifier, entry in state.symbol_table.items()
        }
      ),
      'quality_report_json': json.dumps(state.quality_report.summary()) if state.quality_report else None,
      'conversion_settings_json': json.dumps(state.conversion_settings.__dict__),
      'performance_settings_json': json.dumps(state.performance_settings.__dict__),
      'ai_settings_json': json.dumps(state.ai_settings.__dict__),
      'webhooks_json': json.dumps(state.webhooks),
      'conversion_report_json': json.dumps(state.conversion_report.metadata) if state.conversion_report else None,
      'created_at': state.created_at,
      'updated_at': state.updated_at
    }
    with _connect(self.db_path) as conn:
      conn.execute(
        """
        INSERT INTO conversion_sessions (
          id, project_path, target_path, direction, stage_progress_json, chunks_json,
          paused, summary_notes_json, symbol_table_json,
          quality_report_json, conversion_settings_json, performance_settings_json,
          ai_settings_json, webhooks_json, conversion_report_json,
          created_at, updated_at
        )
        VALUES (
          :id, :project_path, :target_path, :direction, :stage_progress_json, :chunks_json,
          :paused, :summary_notes_json, :symbol_table_json,
          :quality_report_json, :conversion_settings_json, :performance_settings_json,
          :ai_settings_json, :webhooks_json, :conversion_report_json,
          :created_at, :updated_at
        )
        ON CONFLICT(id) DO UPDATE SET
          project_path=excluded.project_path,
          target_path=excluded.target_path,
          direction=excluded.direction,
          stage_progress_json=excluded.stage_progress_json,
          chunks_json=excluded.chunks_json,
          paused=excluded.paused,
          summary_notes_json=excluded.summary_notes_json,
          symbol_table_json=excluded.symbol_table_json,
          quality_report_json=excluded.quality_report_json,
          conversion_settings_json=excluded.conversion_settings_json,
          performance_settings_json=excluded.performance_settings_json,
          ai_settings_json=excluded.ai_settings_json,
          webhooks_json=excluded.webhooks_json,
          conversion_report_json=excluded.conversion_report_json,
          created_at=excluded.created_at,
          updated_at=excluded.updated_at;
        """,
        payload
      )
      conn.commit()

  def load(self, session_id: str) -> Optional[SessionState]:
    with _connect(self.db_path) as conn:
      row = conn.execute(
        'SELECT * FROM conversion_sessions WHERE id = ?',
        (session_id,)
      ).fetchone()
      if not row:
        return None
      stage_progress = {
        Stage[key]: StageProgress(
          stage=Stage[key],
          completed_units=value['completed_units'],
          total_units=value['total_units'],
          status=value['status']
        )
        for key, value in json.loads(row['stage_progress_json']).items()
      }
      chunks_data = json.loads(row['chunks_json'])
      chunks: Dict[str, ChunkRecord] = {}
      for chunk_id, entry in chunks_data.items():
        chunk = ChunkRecord(
          chunk=_reconstruct_chunk(entry),
          status=ChunkStatus[entry['status']],
          output_path=Path(entry['output_path']) if entry['output_path'] else None,
          tokens_used=entry['tokens_used'],
          input_tokens=entry.get('input_tokens', 0),
          output_tokens=entry.get('output_tokens', 0),
          cost_usd=entry['cost_usd'],
          summary=entry['summary'],
          last_error=entry['last_error'],
          partial_completion=entry.get('partial_completion', False),
          ai_model=entry.get('ai_model'),
          provider_id=entry.get('provider_id'),
          raw_output=entry.get('raw_output')
        )
        chunks[chunk_id] = chunk
      symbol_table_entries = {
        identifier: _reconstruct_symbol_entry(identifier, data)
        for identifier, data in json.loads(row['symbol_table_json']).items()
      }

      quality_report = None
      if row['quality_report_json']:
        report_data = json.loads(row['quality_report_json'])
        quality_report = QualityReport(
          issues=[QualityIssue(**issue) for issue in report_data.get('issues', [])],
          syntax_passed=report_data.get('syntax_passed', True),
          build_passed=report_data.get('build_passed', True),
          dependency_ok=report_data.get('dependency_ok', True),
          resources_ok=report_data.get('resources_ok', True),
          api_ok=report_data.get('api_ok', True),
          security_ok=report_data.get('security_ok', True),
          ai_review_notes=report_data.get('ai_review_notes', []),
          flagged_chunks=report_data.get('flagged_chunks', [])
        )

      conversion_report = None
      if row['conversion_report_json']:
        conversion_report = ConversionReport(
          summary_html=Path(row['target_path']) / 'reports' / 'conversion_report.html',
          diff_artifacts=[],
          generated_at=row['updated_at'],
          metadata=json.loads(row['conversion_report_json'])
        )

      return SessionState(
        session_id=row['id'],
        project_path=Path(row['project_path']),
        target_path=Path(row['target_path']),
        direction=row['direction'],
        stage_progress=stage_progress,
        chunks=chunks,
        created_at=row['created_at'],
        updated_at=row['updated_at'],
        paused=bool(row['paused']),
        summary_notes=json.loads(row['summary_notes_json']),
        symbol_table=symbol_table_entries,
        quality_report=quality_report,
        conversion_settings=_reconstruct_settings(json.loads(row['conversion_settings_json'])) if row['conversion_settings_json'] else ConversionSettings(),
        performance_settings=_reconstruct_performance(json.loads(row['performance_settings_json'])) if row['performance_settings_json'] else PerformanceSettings(),
        ai_settings=_reconstruct_ai(json.loads(row['ai_settings_json'])) if row['ai_settings_json'] else AISettings(),
        webhooks=json.loads(row['webhooks_json']) if row['webhooks_json'] else [],
        conversion_report=conversion_report
      )


  def _ensure_column(self, conn: sqlite3.Connection, column: str, definition: str) -> None:
    info = conn.execute('PRAGMA table_info(conversion_sessions)').fetchall()
    if column in {row['name'] for row in info}:
      return
    conn.execute(f'ALTER TABLE conversion_sessions ADD COLUMN {column} {definition}')


def _reconstruct_chunk(entry: Dict[str, Any]) -> Any:
  from backend.conversion.models import ChunkWorkItem, Stage

  return ChunkWorkItem(
    file_path=Path(entry['file_path']),
    language=entry.get('language', 'unknown'),
    start_line=entry.get('start_line', 0),
    end_line=entry.get('end_line', 0),
    content='',
    stage=Stage[entry['stage']],
    chunk_id=entry.get('chunk_id', entry['file_path'])
  )


def _reconstruct_symbol_entry(identifier: str, payload: Dict[str, Any]) -> Any:
  from backend.conversion.models import SymbolTableEntry

  return SymbolTableEntry(
    identifier=identifier,
    kind=payload.get('kind', 'symbol'),
    location=payload.get('location', ''),
    metadata=payload.get('metadata', {})
  )


def _reconstruct_settings(payload: Dict[str, Any]) -> ConversionSettings:
  return ConversionSettings(**payload)


def _reconstruct_performance(payload: Dict[str, Any]) -> PerformanceSettings:
  return PerformanceSettings(**payload)


def _reconstruct_ai(payload: Dict[str, Any]) -> AISettings:
  return AISettings(**payload)
