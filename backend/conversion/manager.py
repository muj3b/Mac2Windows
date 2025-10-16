from __future__ import annotations

import asyncio
import logging
import shutil
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from backend.ai.model_router import ModelRouter
from backend.ai.clients import ProviderError
from backend.ai.orchestrator import AIOrchestrator, OrchestrationConfig
from backend.conversion.chunker import generate_work_plan
from backend.conversion.mappings import ApiMappingCatalog, DependencyMapping
from backend.conversion.models import (
  ChunkRecord,
  ChunkStatus,
  ChunkWorkItem,
  ConversionSummary,
  ConversionSettings,
  PerformanceSettings,
  AISettings,
  QualityReport,
  QualityIssue,
  ConversionReport,
  SessionState,
  Stage,
  StageProgress,
  STAGE_ORDER,
  SymbolTableEntry
)
from backend.conversion.progress import ProgressTracker
from backend.conversion.rag import RagContextBuilder
from backend.conversion.session_store import ConversionSessionStore
from backend.resources.monitor import ResourceMonitor
from backend.quality.engine import QualityEngine
from backend.storage.backup import create_backup
from backend.performance.benchmark import run_benchmarks
from backend.conversion.resources import ResourceConverter
from backend.conversion.dependencies import DependencyGenerator
from backend.conversion.project import ProjectGenerator
from backend.conversion.validators import ValidationEngine
from backend.security.licenses import LicenseScanner
from backend.security.vulnerabilities import VulnerabilityScanner
from backend.conversion.git_utils import GitHandler
from backend.conversion.incremental import IncrementalState, calculate_checksum
from backend.config import settings

logger = logging.getLogger(__name__)

SAVE_INTERVAL_SECONDS = 30
RESOURCE_THROTTLE_SLEEP = 5


@dataclass
class ConversionSession:
  session_id: str
  project_path: Path
  target_path: Path
  direction: str
  orchestrator_config: OrchestrationConfig
  conversion_settings: ConversionSettings
  performance_settings: PerformanceSettings
  ai_settings: AISettings
  progress: ProgressTracker
  work_plan: Dict[Stage, List[ChunkWorkItem]]
  chunks: Dict[str, ChunkRecord] = field(default_factory=dict)
  summary_notes: List[str] = field(default_factory=list)
  symbol_table: Dict[str, SymbolTableEntry] = field(default_factory=dict)
  quality_report: QualityReport = field(default_factory=QualityReport)
  conversion_report: Optional[ConversionReport] = None
  webhooks: List[str] = field(default_factory=list)
  paused: bool = False
  created_at: float = field(default_factory=time.time)
  updated_at: float = field(default_factory=time.time)
  task: Optional[asyncio.Task] = None
  last_save: float = field(default_factory=time.time)
  last_chunk_summary: Dict[str, str] = field(default_factory=dict)


class ConversionManager:
  def __init__(
    self,
    provider_registry,
    dependency_mapping: DependencyMapping,
    api_mapping: ApiMappingCatalog,
    embedding_store,
    session_store: ConversionSessionStore,
    resource_monitor: ResourceMonitor,
    event_logger=None,
    learning_memory=None
  ) -> None:
    self.provider_registry = provider_registry
    self.dependency_mapping = dependency_mapping
    self.api_mapping = api_mapping
    self.rag_builder = RagContextBuilder(embedding_store)
    self.session_store = session_store
    self.resource_monitor = resource_monitor
    self.model_router = ModelRouter(provider_registry)
    self.orchestrator = AIOrchestrator(provider_registry, dependency_mapping, api_mapping, self.model_router)
    self.quality_engine = QualityEngine(dependency_mapping, api_mapping, self.orchestrator)
    self.event_logger = event_logger
    self.learning_memory = learning_memory
    self.debug_mode = False
    self.resource_converter = ResourceConverter()
    self.dependency_generator = DependencyGenerator()
    self.project_generator = ProjectGenerator()
    self.validation_engine = ValidationEngine()
    self.license_scanner = LicenseScanner()
    self.vulnerability_scanner = VulnerabilityScanner()
    self.git_handler = GitHandler(Path.cwd())
    self.incremental_cache = IncrementalState.load(settings.incremental_cache_path)
    self.sessions: Dict[str, ConversionSession] = {}

  def active_sessions(self) -> List[str]:
    return list(self.sessions.keys())

  def get_summary(self, session_id: str) -> Optional[ConversionSummary]:
    session = self.sessions.get(session_id)
    if session:
      summary = session.progress.summary()
      summary.quality_report = session.quality_report
      summary.conversion_report = session.conversion_report
      return summary
    state = self.session_store.load(session_id)
    if not state:
      return None
    tracker = ProgressTracker(direction=state.direction)
    for stage, progress in state.stage_progress.items():
      tracker.stage_progress[stage] = progress
    tracker.total_chunks = len(state.chunks)
    tracker.completed_chunks = sum(
      1 for record in state.chunks.values() if record.status == ChunkStatus.COMPLETED
    )
    summary = tracker.summary()
    summary.quality_report = state.quality_report
    summary.conversion_report = state.conversion_report
    return summary

  def pause_session(self, session_id: str) -> bool:
    session = self.sessions.get(session_id)
    if not session:
      return False
    session.paused = True
    session.progress.pause()
    return True

  def resume_session(self, session_id: str) -> bool:
    session = self.sessions.get(session_id)
    if not session:
      return False
    session.paused = False
    session.progress.resume()
    return True

  def start_session(
    self,
    project_path: Path,
    target_path: Path,
    direction: str,
    provider_id: str,
    model_identifier: str,
    api_key: Optional[str] = None,
    conversion_settings: Optional[ConversionSettings] = None,
    performance_settings: Optional[PerformanceSettings] = None,
    ai_settings: Optional[AISettings] = None,
    webhooks: Optional[List[str]] = None,
    incremental: bool = False
  ) -> ConversionSession:
    session_id = uuid.uuid4().hex[:12]
    work_plan = generate_work_plan(project_path, direction)
    progress = ProgressTracker(direction=direction)
    for stage in STAGE_ORDER:
      chunks = work_plan.get(stage, [])
      progress.ensure_stage(stage, len(chunks))
      if stage == Stage.QUALITY and not chunks:
        stage_progress = progress.stage_progress[stage]
        stage_progress.total_units = 1
        stage_progress.completed_units = 1
        stage_progress.status = 'skipped'

    self.rag_builder.index_project(project_path)

    session = ConversionSession(
      session_id=session_id,
      project_path=project_path,
      target_path=target_path,
      direction=direction,
      orchestrator_config=OrchestrationConfig(
        provider_id=provider_id,
        model_identifier=model_identifier,
        api_key=api_key,
        temperature=ai_settings.temperature,
        max_tokens=4096
      ),
      conversion_settings=conversion_settings or ConversionSettings(),
      performance_settings=performance_settings or PerformanceSettings(),
      ai_settings=ai_settings or AISettings(),
      webhooks=webhooks or [],
      progress=progress,
      work_plan=work_plan,
      incremental=incremental
    )

    for stage, chunks in work_plan.items():
      for chunk in chunks:
        record = ChunkRecord(chunk=chunk)
        session.chunks[chunk.chunk_id] = record
        session.progress.register_chunk(record)

    # Tune resource thresholds based on performance settings
    self.resource_monitor.thresholds.cpu_percent = session.performance_settings.max_cpu
    self.resource_monitor.thresholds.memory_percent = min(
      99.0,
      float(session.performance_settings.max_ram_gb) / 32.0 * 100.0
    )

    self.sessions[session_id] = session
    if session.incremental:
      self._mark_skipped_chunks(session)
    session.task = asyncio.create_task(self._run_session(session))
    if self.git_handler:
      self.git_handler.commit_snapshot(f'Start conversion {session_id}')
    logger.info('Started conversion session %s', session_id)
    if self.event_logger:
      self.event_logger.log_event(
        'session_start',
        'Conversion session started',
        {
          'session_id': session_id,
          'direction': direction,
          'provider': provider_id,
          'model': model_identifier
        }
      )
    return session

  async def _run_session(self, session: ConversionSession) -> None:
    try:
      for stage in STAGE_ORDER:
        if stage == Stage.QUALITY:
          await self._run_quality_stage(session)
          continue
        chunks = session.work_plan.get(stage, [])
        if stage == Stage.TESTS and not chunks:
          await self._run_validation_stage(session)
          session.progress.ensure_stage(stage, 1)
          session.progress.stage_progress[stage].completed_units = 1
          session.progress.stage_progress[stage].status = 'completed'
          await self._persist_session(session)
          continue
        if not chunks:
          session.progress.ensure_stage(stage, 0)
          session.progress.complete_stage(stage)
          await self._persist_session(session)
          continue
        session.progress.start_stage(stage)
        for chunk in chunks:
          record = session.chunks[chunk.chunk_id]
          if record.status == ChunkStatus.COMPLETED:
            continue
          await self._respect_pause(session)
          await self._respect_system_load()
          await self._process_chunk(session, record)
          await self._persist_session(session)
        session.progress.complete_stage(stage)
        await self._persist_session(session)
    except asyncio.CancelledError:
      logger.info('Conversion session %s cancelled', session.session_id)
    except Exception as err:  # pragma: no cover - defensive
      logger.exception('Conversion session %s failed: %s', session.session_id, err)
      if self.event_logger:
        self.event_logger.log_error(
          'Conversion session failed',
          {
            'session_id': session.session_id,
            'error': str(err)
          }
        )
    finally:
      session.updated_at = time.time()

  async def _respect_pause(self, session: ConversionSession) -> None:
    while session.paused:
      await asyncio.sleep(0.5)

  async def _respect_system_load(self) -> None:
    snapshot = self.resource_monitor.snapshot()
    flags = snapshot.get('flags', {})
    if flags.get('cpu_high') or flags.get('memory_high'):
      logger.warning('Throttling conversion due to high system load')
      await asyncio.sleep(RESOURCE_THROTTLE_SLEEP)

  async def _process_chunk(self, session: ConversionSession, record: ChunkRecord) -> None:
    chunk = record.chunk
    if chunk.stage == Stage.RESOURCES:
      await self._handle_resource_chunk(session, record)
      return
    if chunk.stage == Stage.DEPENDENCIES:
      await self._handle_dependency_chunk(session, record)
      return
    if chunk.stage == Stage.PROJECT_SETUP:
      await self._handle_project_chunk(session, record)
      return
    if chunk.stage == Stage.TESTS:
      await self._handle_validation_chunk(session, record)
      return

    context = self.rag_builder.query_context(chunk)
    previous_summary = session.last_chunk_summary.get(chunk.file_path.as_posix())
    learning_hints = []
    if self.learning_memory:
      hints = self.learning_memory.suggestions(chunk.content)
      learning_hints = hints.get('matches', [])
    try:
      result = await self.orchestrator.convert_chunk(
        chunk=chunk,
        config=session.orchestrator_config,
        ai_settings=session.ai_settings,
        direction=session.direction,
        rag_context=context,
        previous_summary=previous_summary,
        learning_hints=learning_hints
      )
    except ProviderError as exc:
      record.status = ChunkStatus.FAILED
      record.last_error = str(exc)
      session.summary_notes.append(f'Provider error on {chunk.chunk_id}: {exc}')
      if self.event_logger:
        self.event_logger.log_error('provider_error', {'session_id': session.session_id, 'chunk_id': chunk.chunk_id, 'error': str(exc)})
      raise

    output_text = result['output_text']
    summary = result['summary']
    prompt_metadata = result.get('prompt_metadata', {})
    tokens_used = result.get('tokens_used', 0)
    cost_usd = result.get('cost_usd', 0.0)
    stopped_early = result.get('stopped_early', False)

    output_path = self._determine_output_path(session, chunk)

    record.raw_output = output_text
    record.status = ChunkStatus.COMPLETED if not stopped_early else ChunkStatus.IN_PROGRESS
    record.tokens_used = tokens_used
    record.input_tokens = result.get('input_tokens', 0)
    record.output_tokens = result.get('output_tokens', 0)
    record.cost_usd = cost_usd
    record.summary = summary
    record.output_path = output_path
    record.ai_model = result.get('model_identifier')
    record.provider_id = result.get('provider_id')
    record.partial_completion = stopped_early
    if stopped_early:
      record.last_error = result.get('last_error', 'Model halted early; instructing resume.')

    session.summary_notes.append(summary)
    session.last_chunk_summary[chunk.file_path.as_posix()] = summary
    self.rag_builder.register_chunk(chunk, summary, output_text)
    session.symbol_table.update(self._extract_symbols(chunk))
    session.progress.update_chunk(record)

    if chunk.stage == Stage.CODE:
      self._assemble_file_if_ready(session, chunk.chunk.file_path)
    else:
      if chunk.language == 'asset-bundle':
        output_path.mkdir(parents=True, exist_ok=True)
        placeholder = output_path / 'conversion-placeholder.txt'
        placeholder.write_text(output_text, encoding='utf-8')
      else:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output_text, encoding='utf-8')

    if stopped_early:
      logger.info('Chunk %s incomplete; scheduling resume message', chunk.chunk_id)
      await self._resume_incomplete_chunk(session, record)
    else:
      if record.chunk.checksum:
        self.incremental_cache.update_checksum(record.chunk.file_path, record.chunk.checksum)
    if self.event_logger:
      self.event_logger.log_event(
        'chunk_complete',
        'Chunk processed',
        {
          'session_id': session.session_id,
          'chunk_id': chunk.chunk_id,
          'status': record.status.name,
          'tokens_used': record.tokens_used,
          'cost_usd': record.cost_usd
        }
      )
      if self.debug_mode:
        self.event_logger.log_event(
          'debug_prompt',
          'LLM invocation',
          {
            'session_id': session.session_id,
            'chunk_id': chunk.chunk_id,
            'prompt_metadata': prompt_metadata
          }
        )

  async def _run_quality_stage(self, session: ConversionSession) -> None:
    stage = Stage.QUALITY
    session.progress.start_stage(stage)
    report = await self.quality_engine.evaluate(session)
    session.quality_report = report
    if self.learning_memory and report.issues:
      for issue in report.issues:
        self.learning_memory.record(issue.category, issue.message)
    stage_progress = session.progress.stage_progress[stage]
    stage_progress.completed_units = max(1, stage_progress.completed_units or 0)
    stage_progress.total_units = max(1, stage_progress.total_units or 1)
    stage_progress.status = 'completed'
    quality_record = ChunkRecord(
      chunk=ChunkWorkItem(
        file_path=session.target_path / 'QUALITY_REPORT',
        language='report',
        start_line=0,
        end_line=0,
        content='Quality report generated',
        stage=stage,
        chunk_id='quality-report'
      ),
      status=ChunkStatus.COMPLETED,
      summary='Quality assurance complete'
    )
    session.chunks['quality-report'] = quality_record
    session.progress.update_chunk(quality_record)
    await self._generate_reports(session)
    backup_path = create_backup(session.target_path, session.target_path / 'backups')
    session.summary_notes.append(f'Backup created: {backup_path}')
    await self._trigger_webhooks(session)
    await self._persist_session(session)
    session.updated_at = time.time()
    if self.event_logger:
      self.event_logger.log_event(
        'quality_complete',
        'Quality assurance completed',
        {
          'session_id': session.session_id,
          'issues': [issue.__dict__ for issue in report.issues]
        }
      )

  async def _resume_incomplete_chunk(self, session: ConversionSession, record: ChunkRecord) -> None:
    chunk = record.chunk
    resume_chunk = ChunkWorkItem(
      file_path=chunk.file_path,
      language=chunk.language,
      start_line=chunk.start_line,
      end_line=chunk.end_line,
      content="Continue exactly where you stopped. Complete the conversion without repeating prior output.",
      stage=chunk.stage,
      chunk_id=f'{chunk.chunk_id}-resume'
    )
    resume_record = ChunkRecord(chunk=resume_chunk, status=ChunkStatus.PENDING)
    session.chunks[resume_chunk.chunk_id] = resume_record
    session.work_plan[chunk.stage].append(resume_chunk)

  def _determine_output_path(self, session: ConversionSession, chunk: ChunkWorkItem) -> Path:
    relative = chunk.file_path.relative_to(session.project_path)
    if session.direction == 'mac-to-win':
      replacement = self._mac_to_windows_path(relative)
    else:
      replacement = self._windows_to_mac_path(relative)
    return session.target_path / replacement

  def _mac_to_windows_path(self, relative: Path) -> Path:
    mapping = {
      '.swift': '.cs',
      '.m': '.cs',
      '.mm': '.cs',
      '.xib': '.xaml',
      '.storyboard': '.xaml',
      '.strings': '.resx',
      '.plist': '.app.manifest',
      '.xcassets': '.resources'
    }
    suffix = relative.suffix.lower()
    new_suffix = mapping.get(suffix, suffix)
    if suffix == '.xcassets':
      return Path('Resources') / relative.with_suffix('')
    return relative.with_suffix(new_suffix)

  def _windows_to_mac_path(self, relative: Path) -> Path:
    mapping = {
      '.cs': '.swift',
      '.xaml': '.storyboard',
      '.resx': '.strings',
      '.app.manifest': '.plist'
    }
    suffix = relative.suffix.lower()
    new_suffix = mapping.get(suffix, suffix)
    if suffix == '.resx':
      return Path('Localization') / relative.with_suffix('.strings')
    return relative.with_suffix(new_suffix)

  def _assemble_file_if_ready(self, session: ConversionSession, source_path: Path) -> None:
    records = [rec for rec in session.chunks.values() if rec.chunk.file_path == source_path]
    if not records:
      return
    if any(rec.status != ChunkStatus.COMPLETED or rec.raw_output is None for rec in records):
      return
    ordered = sorted(records, key=lambda rec: (rec.chunk.start_line, rec.chunk.end_line))
    combined = self._stitch_chunks(ordered)
    output_path = ordered[0].output_path or self._determine_output_path(session, ordered[0].chunk)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(combined, encoding='utf-8')

  def _stitch_chunks(self, records: List[ChunkRecord]) -> str:
    parts: List[str] = []
    for record in records:
      part = (record.raw_output or '').strip('\n')
      parts.append(part)
    combined = '\n\n'.join(part for part in parts if part)
    if not combined.endswith('\n'):
      combined += '\n'
    return combined

  async def _run_validation_stage(self, session: ConversionSession) -> List[QualityIssue]:
    if session.direction == 'mac-to-win':
      issues = self.validation_engine.validate_windows_project(session.target_path)
    else:
      issues = self.validation_engine.validate_mac_project(session.target_path)
    for issue in issues:
      session.summary_notes.append(f'Validation issue: {issue.message}')
    return issues

  def _extract_symbols(self, chunk: ChunkWorkItem) -> Dict[str, SymbolTableEntry]:
    symbols = {}
    for symbol in chunk.symbols:
      symbols[symbol] = SymbolTableEntry(
        identifier=symbol,
        kind='symbol',
        location=str(chunk.file_path),
        metadata={'stage': chunk.stage.name, 'language': chunk.language}
      )
    return symbols

  async def _handle_resource_chunk(self, session: ConversionSession, record: ChunkRecord) -> None:
    target_path = self._determine_output_path(session, record.chunk)
    outputs = self.resource_converter.convert(session.direction, record.chunk, target_path)
    record.status = ChunkStatus.COMPLETED
    record.output_path = outputs[0] if outputs else target_path
    record.summary = f'Resource converted to {record.output_path}'
    session.summary_notes.append(record.summary)
    session.progress.update_chunk(record)

  async def _handle_dependency_chunk(self, session: ConversionSession, record: ChunkRecord) -> None:
    if session.direction == 'mac-to-win':
      output = self.dependency_generator.convert_to_windows(session.project_path, session.target_path)
    else:
      output = self.dependency_generator.convert_to_mac(session.project_path, session.target_path)
    license_issues = self.license_scanner.scan(session.target_path)
    vuln_issues: List[QualityIssue] = []
    if output.suffix == '.config':
      vuln_issues = self.vulnerability_scanner.scan_packages_config(output)
    elif output.suffix == '.swift':
      vuln_issues = self.vulnerability_scanner.scan_package_swift(output)
    for issue in license_issues + vuln_issues:
      session.summary_notes.append(f'License/security: {issue.message}')
      if session.quality_report:
        session.quality_report.issues.append(issue)
    record.status = ChunkStatus.COMPLETED
    record.output_path = output
    record.summary = f'Dependencies generated at {output.name}'
    session.summary_notes.append(record.summary)
    session.progress.update_chunk(record)

  async def _handle_project_chunk(self, session: ConversionSession, record: ChunkRecord) -> None:
    if session.direction == 'mac-to-win':
      output = self.project_generator.create_windows_project(session.target_path, session.conversion_settings)
    else:
      output = self.project_generator.create_mac_project(session.target_path, session.conversion_settings)
    record.status = ChunkStatus.COMPLETED
    record.output_path = output
    record.summary = f'Project structure generated at {output}'
    session.summary_notes.append(record.summary)
    session.progress.update_chunk(record)

  async def _handle_validation_chunk(self, session: ConversionSession, record: ChunkRecord) -> None:
    issues = await self._run_validation_stage(session)
    record.status = ChunkStatus.COMPLETED
    record.summary = 'Validation completed' if not issues else 'Validation completed with issues'
    session.summary_notes.append(record.summary)
    session.progress.update_chunk(record)

  async def _persist_session(self, session: ConversionSession) -> None:
    now = time.time()
    if now - session.last_save < SAVE_INTERVAL_SECONDS and not session.progress.paused:
      return
    state = SessionState(
      session_id=session.session_id,
      project_path=session.project_path,
      target_path=session.target_path,
      direction=session.direction,
      stage_progress=session.progress.stage_progress,
      chunks=session.chunks,
      created_at=session.created_at,
      updated_at=now,
      paused=session.paused,
      summary_notes=session.summary_notes,
      symbol_table=session.symbol_table,
      quality_report=session.quality_report,
      conversion_settings=session.conversion_settings,
      performance_settings=session.performance_settings,
      ai_settings=session.ai_settings,
      webhooks=session.webhooks,
      conversion_report=session.conversion_report
    )
    self.session_store.upsert(state)
    session.last_save = now

  async def _generate_reports(self, session: ConversionSession) -> None:
    from backend.reports.generator import generate_conversion_report

    session.conversion_report = generate_conversion_report(session)
    session.summary_notes.append(f"Quality report generated: {session.conversion_report.summary_html}")
    benchmark = run_benchmarks(session.project_path, session.target_path)
    session.summary_notes.append(f"Benchmark: mac={benchmark['mac_duration']} win={benchmark['win_duration']}")

  async def _trigger_webhooks(self, session: ConversionSession) -> None:
    if not session.webhooks:
      return
    if not session.conversion_report:
      return
    import json
    import requests

    payload = json.dumps(session.conversion_report.metadata)
    headers = {'Content-Type': 'application/json'}
    for url in session.webhooks:
      try:
        requests.post(url, data=payload, headers=headers, timeout=5)
      except Exception as error:  # pragma: no cover - network optional
        logger.warning('Webhook %s failed: %s', url, error)

  def set_debug_mode(self, enabled: bool) -> None:
    self.debug_mode = enabled

  def rollback(self, session_id: str, backup_path: Optional[Path] = None) -> Path:
    session = self.sessions.get(session_id)
    target_path: Optional[Path] = None
    if session:
      target_path = session.target_path
    else:
      state = self.session_store.load(session_id)
      if state:
        target_path = state.target_path
    if not target_path:
      raise ValueError('Session not found')

    backups_dir = target_path / 'backups'
    if backup_path is None:
      archives = sorted(backups_dir.glob('conversion_backup_*.zip'), key=lambda p: p.stat().st_mtime, reverse=True)
      if not archives:
        raise FileNotFoundError('No backups available')
      backup_path = archives[0]
    restore_dir = target_path.parent / f'{target_path.name}_rollback'
    restore_dir.mkdir(parents=True, exist_ok=True)
    shutil.unpack_archive(str(backup_path), str(restore_dir))
    if self.event_logger:
      self.event_logger.log_event(
        'rollback',
        'Rollback prepared',
        {
          'session_id': session_id,
          'backup': str(backup_path),
          'restore_dir': str(restore_dir)
        }
      )
    return restore_dir

  async def close(self) -> None:
    await self.orchestrator.close()
