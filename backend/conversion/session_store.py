from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

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
  AISettings,
  GitSettings,
  BackupSettings,
  ManualFixEntry,
  CostSettings,
  CleanupReport,
  PreviewEstimate
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
          backup_settings_json TEXT,
          webhooks_json TEXT,
          conversion_report_json TEXT,
          git_settings_json TEXT,
          incremental INTEGER DEFAULT 0,
          manual_queue_json TEXT,
          test_results_json TEXT,
          benchmarks_json TEXT,
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
        ('backup_settings_json', 'TEXT'),
        ('webhooks_json', 'TEXT'),
        ('conversion_report_json', 'TEXT'),
        ('git_settings_json', 'TEXT'),
        ('incremental', 'INTEGER'),
        ('manual_queue_json', 'TEXT'),
        ('test_results_json', 'TEXT'),
        ('benchmarks_json', 'TEXT'),
        ('cost_settings_json', 'TEXT'),
        ('cleanup_report_json', 'TEXT'),
        ('preview_estimate_json', 'TEXT')
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
      'backup_settings_json': json.dumps(state.backup_settings.__dict__),
      'webhooks_json': json.dumps(state.webhooks),
      'conversion_report_json': json.dumps(state.conversion_report.metadata) if state.conversion_report else None,
      'git_settings_json': json.dumps(state.git_settings.__dict__),
      'incremental': 1 if state.incremental else 0,
      'manual_queue_json': json.dumps({key: entry.to_dict() for key, entry in state.manual_queue.items()}),
      'test_results_json': json.dumps(state.test_results) if state.test_results else None,
      'benchmarks_json': json.dumps(state.benchmarks) if state.benchmarks else None,
      'cost_settings_json': json.dumps(state.cost_settings.__dict__) if state.cost_settings else None,
      'cleanup_report_json': json.dumps(state.cleanup_report.summary()) if state.cleanup_report else None,
      'preview_estimate_json': json.dumps(state.preview_estimate.summary()) if state.preview_estimate else None,
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
          ai_settings_json, backup_settings_json, webhooks_json, conversion_report_json, git_settings_json, incremental, manual_queue_json, test_results_json, benchmarks_json,
          cost_settings_json, cleanup_report_json, preview_estimate_json, created_at, updated_at
        )
        VALUES (
          :id, :project_path, :target_path, :direction, :stage_progress_json, :chunks_json,
          :paused, :summary_notes_json, :symbol_table_json,
          :quality_report_json, :conversion_settings_json, :performance_settings_json,
          :ai_settings_json, :backup_settings_json, :webhooks_json, :conversion_report_json, :git_settings_json, :incremental, :manual_queue_json, :test_results_json, :benchmarks_json,
          :cost_settings_json, :cleanup_report_json, :preview_estimate_json, :created_at, :updated_at
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
          backup_settings_json=excluded.backup_settings_json,
          webhooks_json=excluded.webhooks_json,
          conversion_report_json=excluded.conversion_report_json,
          git_settings_json=excluded.git_settings_json,
          incremental=excluded.incremental,
          manual_queue_json=excluded.manual_queue_json,
          test_results_json=excluded.test_results_json,
          benchmarks_json=excluded.benchmarks_json,
          cost_settings_json=excluded.cost_settings_json,
          cleanup_report_json=excluded.cleanup_report_json,
          preview_estimate_json=excluded.preview_estimate_json,
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

      git_settings = GitSettings(**json.loads(row['git_settings_json'])) if row['git_settings_json'] else GitSettings()
      incremental = bool(row['incremental']) if 'incremental' in row.keys() else False
      backup_settings = BackupSettings(**json.loads(row['backup_settings_json'])) if row['backup_settings_json'] else BackupSettings()
      manual_queue_payload = json.loads(row['manual_queue_json']) if row['manual_queue_json'] else {}
      manual_queue = {
        key: ManualFixEntry(
          chunk_id=value.get('chunk_id', key),
          file_path=value.get('file_path', ''),
          reason=value.get('reason', ''),
          notes=value.get('notes', []),
          status=value.get('status', 'pending'),
          override_path=value.get('override_path'),
          submitted_by=value.get('submitted_by'),
          timestamp=value.get('timestamp'),
          fingerprint=value.get('fingerprint')
        )
        for key, value in manual_queue_payload.items()
      }
      test_results = json.loads(row['test_results_json']) if row['test_results_json'] else None
      benchmarks = json.loads(row['benchmarks_json']) if row['benchmarks_json'] else {}
      cost_settings = CostSettings(**json.loads(row['cost_settings_json'])) if row['cost_settings_json'] else CostSettings()
      cleanup_report = None
      if row['cleanup_report_json']:
        cleanup_data = json.loads(row['cleanup_report_json'])
        cleanup_report = CleanupReport(
          unused_assets=cleanup_data.get('unused_assets', []),
          unused_dependencies=cleanup_data.get('unused_dependencies', []),
          total_bytes_reclaimed=cleanup_data.get('total_bytes_reclaimed', 0),
          auto_deleted=cleanup_data.get('auto_deleted', []),
          scanned_assets=cleanup_data.get('scanned_assets', 0),
          scanned_dependencies=cleanup_data.get('scanned_dependencies', 0)
        )
      preview_estimate = None
      if row['preview_estimate_json']:
        preview_data = json.loads(row['preview_estimate_json'])
        preview_estimate = PreviewEstimate(
          total_files=preview_data.get('total_files', 0),
          impacted_files=preview_data.get('impacted_files', 0),
          estimated_tokens=preview_data.get('estimated_tokens', 0),
          estimated_cost_usd=preview_data.get('estimated_cost_usd', 0.0),
          estimated_minutes=preview_data.get('estimated_minutes', 0.0),
          stage_breakdown=preview_data.get('stage_breakdown', {})
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
        backup_settings=backup_settings,
        webhooks=json.loads(row['webhooks_json']) if row['webhooks_json'] else [],
        conversion_report=conversion_report,
        incremental=incremental,
        git_settings=git_settings,
        manual_queue=manual_queue,
        test_results=test_results,
        benchmarks=benchmarks,
        cost_settings=cost_settings,
        cleanup_report=cleanup_report,
        preview_estimate=preview_estimate
      )


  def statistics(self) -> Dict[str, Any]:
    with _connect(self.db_path) as conn:
      rows = conn.execute(
        'SELECT id, direction, stage_progress_json, chunks_json, quality_report_json FROM conversion_sessions'
      ).fetchall()
    total_cost = 0.0
    directions: Dict[str, int] = {}
    completed = 0
    quality_scores: List[float] = []
    leaderboard: List[Dict[str, Any]] = []

    for row in rows:
      direction = row['direction']
      directions[direction] = directions.get(direction, 0) + 1
      chunks_data = json.loads(row['chunks_json'])
      total_cost += sum(entry.get('cost_usd', 0.0) for entry in chunks_data.values())
      stage_progress = json.loads(row['stage_progress_json'])
      if all(progress.get('status') == 'completed' for progress in stage_progress.values()):
        completed += 1
      quality_score = None
      if row['quality_report_json']:
        report_data = json.loads(row['quality_report_json'])
        issues = report_data.get('issues', [])
        severe = sum(1 for issue in issues if issue.get('severity', '').lower() in {'error', 'critical'})
        quality_score = max(0.0, 1.0 - (severe * 0.2 + len(issues) * 0.05))
        quality_scores.append(quality_score)
        leaderboard.append({'session_id': row['id'], 'score': quality_score, 'issues': len(issues)})

    leaderboard = sorted(leaderboard, key=lambda entry: entry['score'], reverse=True)[:5]
    avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else None
    avg_cost = total_cost / len(rows) if rows else 0.0

    return {
      'total_sessions': len(rows),
      'completed_sessions': completed,
      'avg_cost_usd': round(avg_cost, 4),
      'directions': directions,
      'avg_quality_score': round(avg_quality, 3) if avg_quality is not None else None,
      'leaderboard': leaderboard
    }

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
