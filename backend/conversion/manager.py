from __future__ import annotations

import asyncio
import logging
import shutil
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

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
  GitSettings,
  BackupSettings,
  QualityReport,
  QualityIssue,
  ManualFixEntry,
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
from backend.performance.benchmark import run_benchmarks
from backend.conversion.resources import ResourceConverter
from backend.conversion.dependencies import DependencyGenerator
from backend.conversion.project import ProjectGenerator
from backend.conversion.validators import ValidationEngine
from backend.conversion.assets import AssetOptimizer
from backend.conversion.tests import TestHarness
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
  backup_settings: BackupSettings
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
  incremental: bool = False
  git_settings: GitSettings = field(default_factory=GitSettings)
  manual_queue: Dict[str, ManualFixEntry] = field(default_factory=dict)
  test_results: Optional[Dict[str, Any]] = None
  benchmarks: Dict[str, Any] = field(default_factory=dict)


class ConversionManager:
  def __init__(
    self,
    provider_registry,
    dependency_mapping: DependencyMapping,
    api_mapping: ApiMappingCatalog,
    embedding_store,
    session_store: ConversionSessionStore,
    resource_monitor: ResourceMonitor,
    backup_manager,
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
    self.incremental_cache = IncrementalState.load(settings.incremental_cache_path)
    self.backup_manager = backup_manager
    self.session_git_handlers: Dict[str, GitHandler] = {}
    self.manual_fix_root = settings.data_dir / 'manual_fixes'
    self.manual_fix_root.mkdir(parents=True, exist_ok=True)
    self.asset_optimizer = AssetOptimizer()
    self.test_harness = TestHarness()
    self.sessions: Dict[str, ConversionSession] = {}

  def active_sessions(self) -> List[str]:
    return list(self.sessions.keys())

  def _summarize_backups(self, session_id: str) -> List[Dict[str, Any]]:
    if not getattr(self, 'backup_manager', None):
      return []
    records = self.backup_manager.list_backups(session_id=session_id)
    return [
      {
        'id': record.id,
        'provider': record.provider,
        'credential_id': record.credential_id,
        'remote_id': record.remote_id,
        'remote_url': record.remote_url,
        'metadata': record.metadata,
        'created_at': record.created_at
      }
      for record in records
    ]

  def get_summary(self, session_id: str) -> Optional[ConversionSummary]:
    session = self.sessions.get(session_id)
    if session:
      summary = session.progress.summary()
      summary.quality_report = session.quality_report
      summary.conversion_report = session.conversion_report
      summary.manual_fixes_pending = sum(1 for entry in session.manual_queue.values() if entry.status != 'applied')
      summary.backups = self._summarize_backups(session_id)
      summary.test_results = session.test_results
      summary.benchmarks = session.benchmarks
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
    summary.manual_fixes_pending = sum(1 for entry in state.manual_queue.values() if entry.status != 'applied')
    summary.backups = self._summarize_backups(session_id)
    summary.test_results = state.test_results
    summary.benchmarks = state.benchmarks
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

  def list_manual_fixes(self, session_id: str) -> List[Dict[str, Any]]:
    session = self.sessions.get(session_id)
    if session:
      return [entry.to_dict() for entry in session.manual_queue.values()]
    state = self.session_store.load(session_id)
    if state:
      return [entry.to_dict() for entry in state.manual_queue.values()]
    return []

  def submit_manual_fix(self, session_id: str, chunk_id: str, code: str, submitted_by: Optional[str] = None, note: Optional[str] = None) -> bool:
    session = self.sessions.get(session_id)
    if not session:
      raise ValueError('Session is not active; manual fixes require an active session.')
    record = session.chunks.get(chunk_id)
    if not record:
      raise ValueError('Chunk not found')
    entry = session.manual_queue.get(chunk_id)
    if not entry:
      entry = ManualFixEntry(chunk_id=chunk_id, file_path=str(record.chunk.file_path), reason='Manual override')
      session.manual_queue[chunk_id] = entry
    entry.status = 'applied'
    entry.submitted_by = submitted_by
    entry.timestamp = time.time()
    if note:
      entry.notes.append(note)
    override_dir = self.manual_fix_root / session_id
    override_dir.mkdir(parents=True, exist_ok=True)
    override_path = override_dir / f'{chunk_id}.txt'
    override_path.write_text(code, encoding='utf-8')
    entry.override_path = str(override_path)

    output_path = self._determine_output_path(session, record.chunk)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(code, encoding='utf-8')

    record.status = ChunkStatus.COMPLETED
    record.output_path = output_path
    record.summary = 'Manual override applied'
    record.raw_output = code
    record.last_error = None
    self.incremental_cache.update_checksum(record.chunk.file_path, calculate_checksum(record.chunk.file_path))
    session.summary_notes.append(f'Manual fix applied for {record.chunk.file_path}')
    session.progress.update_chunk(record)
    if session.quality_report and chunk_id in session.quality_report.flagged_chunks:
      session.quality_report.flagged_chunks.remove(chunk_id)
    self.session_store.upsert(session)
    try:
      self.incremental_cache.save(settings.incremental_cache_path)
    except Exception as exc:  # pragma: no cover
      if self.event_logger:
        self.event_logger.log_error('incremental_save_failed', {'error': str(exc)})
    if self.event_logger:
      self.event_logger.log_event('manual_fix_applied', 'Manual fix applied', {
        'session_id': session_id,
        'chunk_id': chunk_id,
        'submitted_by': submitted_by
      })
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
    incremental: bool = False,
    git_settings: Optional[GitSettings] = None,
    backup_settings: Optional[BackupSettings] = None
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

    git_settings = git_settings or GitSettings(
      enabled=settings.git_enabled,
      tag_after_completion=False,
      tag_prefix=settings.git_tag_prefix,
      branch=settings.git_branch
    )
    conversion_settings = conversion_settings or ConversionSettings()
    performance_settings = performance_settings or PerformanceSettings()
    ai_settings = ai_settings or AISettings()
    backup_settings = backup_settings or BackupSettings()
    if not backup_settings.provider:
      backup_settings.provider = settings.default_backup_provider
    if backup_settings.retention_count <= 0:
      backup_settings.retention_count = settings.backup_retention_count
    if not backup_settings.remote_path:
      backup_settings.remote_path = settings.backup_remote_template

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
      conversion_settings=conversion_settings,
      performance_settings=performance_settings,
      ai_settings=ai_settings,
      backup_settings=backup_settings,
      webhooks=webhooks or [],
      progress=progress,
      work_plan=work_plan,
      incremental=incremental,
      git_settings=git_settings
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
    if session.git_settings.enabled:
      handler = GitHandler(session.target_path, session.git_settings.branch)
      self.session_git_handlers[session.session_id] = handler
      handler.commit_snapshot(f'Pre-conversion snapshot {session.direction} {session_id}')
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
    success = False
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
          if record.status in {ChunkStatus.COMPLETED, ChunkStatus.SKIPPED}:
            if record.status == ChunkStatus.SKIPPED:
              session.progress.stage_progress[chunk.stage].completed_units += 1
              session.progress.completed_chunks += 1
              session.progress.update_chunk(record)
            continue
          if record.status == ChunkStatus.FAILED:
            continue
          await self._respect_pause(session)
          await self._respect_system_load()
          await self._process_chunk(session, record)
          await self._persist_session(session)
        session.progress.complete_stage(stage)
        if stage == Stage.TESTS:
          await self._finalize_tests(session)
        await self._persist_session(session)
      success = True
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
      self._finalize_session(session, success)

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
    manual_entry = session.manual_queue.get(chunk.chunk_id)
    if manual_entry:
      if manual_entry.status == 'applied' and manual_entry.override_path and Path(manual_entry.override_path).exists():
        code = Path(manual_entry.override_path).read_text(encoding='utf-8')
        output_path = self._determine_output_path(session, chunk)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(code, encoding='utf-8')
        record.status = ChunkStatus.COMPLETED
        record.summary = 'Manual override applied'
        record.raw_output = code
        record.output_path = output_path
        record.last_error = None
        session.progress.update_chunk(record)
        session.summary_notes.append(f'Manual override applied for {chunk.file_path}')
        return
      if manual_entry.status == 'pending':
        record.status = ChunkStatus.FAILED
        record.last_error = 'Awaiting manual fix'
        if self.event_logger:
          self.event_logger.log_event('manual_fix_pending', 'Chunk awaiting manual fix', {
            'session_id': session.session_id,
            'chunk_id': chunk.chunk_id
          })
        return

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
      await self._handle_test_chunk(session, record)
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
      self._enqueue_manual_fix(session, record, 'Provider error', str(exc))
      if self.event_logger:
        self.event_logger.log_error('provider_error', {'session_id': session.session_id, 'chunk_id': chunk.chunk_id, 'error': str(exc)})
      return

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

    if chunk.stage == Stage.CODE and session.conversion_settings.self_review and record.status == ChunkStatus.COMPLETED:
      await self._run_self_review(session, record)
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
    benchmarks = run_benchmarks(session.project_path, session.target_path, session.direction)
    session.benchmarks = benchmarks
    regressions = benchmarks.get('regressions') or []
    if regressions:
      for item in regressions:
        message = (
          f"Performance regression detected for {item['metric']} (Δ {item['delta_pct'] * 100:.1f}% vs baseline)"
        )
        session.summary_notes.append(message)
        session.quality_report.issues.append(
          QualityIssue(category='performance', message=message, severity='warning')
        )
    else:
      session.summary_notes.append('Benchmarks completed without regressions.')
    await self._generate_reports(session)
    await self._perform_backup(session)
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

  async def _perform_backup(self, session: ConversionSession) -> None:
    if not self.backup_manager:
      return
    try:
      backup_result = await asyncio.to_thread(self.backup_manager.create_backup, session, session.backup_settings)
    except Exception as exc:  # pragma: no cover - protective path
      message = f'Backup failed: {exc}'
      session.summary_notes.append(message)
      if self.event_logger:
        self.event_logger.log_error('backup_failed', {'session_id': session.session_id, 'error': str(exc)})
      return

    session.summary_notes.append(f'Backup archive created: {backup_result.archive_path}')
    if backup_result.uploaded:
      remote_url = backup_result.uploaded.remote_url or backup_result.uploaded.remote_id
      if remote_url:
        session.summary_notes.append(f'Cloud backup available: {remote_url}')
    if self.event_logger:
      payload = {
        'session_id': session.session_id,
        'archive': str(backup_result.archive_path),
        'metadata': backup_result.metadata,
      }
      if backup_result.uploaded:
        payload['provider'] = backup_result.uploaded.provider
        payload['remote'] = backup_result.uploaded.remote_url or backup_result.uploaded.remote_id
      self.event_logger.log_event('backup_created', 'Conversion backup completed', payload)

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
      if issue.file_path:
        record = self._find_record_by_path(session, Path(issue.file_path))
        if record:
          self._enqueue_manual_fix(session, record, 'Validation failure', issue.message)
    return issues

  async def _run_self_review(self, session: ConversionSession, record: ChunkRecord) -> None:
    chunk = record.chunk
    context = [note for note in session.summary_notes[-5:]]
    review = await self.orchestrator.review_chunk(
      chunk=chunk,
      converted_code=record.raw_output or '',
      config=session.orchestrator_config,
      ai_settings=session.ai_settings,
      direction=session.direction,
      context_summaries=context
    )
    issues = review.get('issues', []) if isinstance(review, dict) else []
    applied_auto_fix = False
    for issue in issues:
      message = issue.get('message', 'Unspecified issue')
      severity = issue.get('severity', 'info')
      auto_fix = issue.get('auto_fix') if isinstance(issue, dict) else None
      manual_note = issue.get('manual_note')
      if auto_fix and isinstance(auto_fix, dict) and auto_fix.get('full_text'):
        new_code = auto_fix['full_text']
        output_path = record.output_path or self._determine_output_path(session, chunk)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(new_code, encoding='utf-8')
        record.raw_output = new_code
        record.output_path = output_path
        session.summary_notes.append(f'Auto-fix applied: {message}')
        applied_auto_fix = True
      else:
        note = manual_note or message
        self._enqueue_manual_fix(session, record, 'Review finding', note)
      if session.quality_report:
        session.quality_report.issues.append(QualityIssue(category='self-review', message=message, severity=severity, file_path=str(chunk.file_path)))

    if applied_auto_fix:
      if record.chunk.checksum:
        self.incremental_cache.update_checksum(record.chunk.file_path, record.chunk.checksum)
      session.progress.update_chunk(record)

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

  def _find_record_by_path(self, session: ConversionSession, file_path: Path) -> Optional[ChunkRecord]:
    for record in session.chunks.values():
      if record.chunk.file_path == file_path:
        return record
      if record.output_path and record.output_path == file_path:
        return record
    return None

  def _mark_skipped_chunks(self, session: ConversionSession) -> None:
    for record in session.chunks.values():
      chunk = record.chunk
      if chunk.stage != Stage.CODE or not chunk.file_path.exists():
        continue
      checksum = calculate_checksum(chunk.file_path)
      chunk.checksum = checksum
      if not self.incremental_cache.is_changed(chunk.file_path, checksum):
        record.status = ChunkStatus.SKIPPED
        record.summary = 'Skipped (unchanged)'
        if self.event_logger:
          self.event_logger.log_event('incremental_skip', 'Chunk skipped', {'chunk_id': chunk.chunk_id})
        session.summary_notes.append(f'Skipped unchanged file {chunk.chunk.file_path}')
    # stage progress will be updated when skipping during run

  def _finalize_session(self, session: ConversionSession, success: bool) -> None:
    if session.git_settings.enabled:
      handler = self.session_git_handlers.pop(session.session_id, None)
      if handler:
        try:
          outcome = 'success' if success else 'failure'
          commit = handler.commit_snapshot(f'Conversion {outcome} {session.direction} {session.session_id}')
          if self.event_logger and commit:
            self.event_logger.log_event('git_commit', 'Conversion snapshot committed', {'session_id': session.session_id, 'commit': commit})
          if success and session.git_settings.tag_after_completion:
            tag_name = f"{session.git_settings.tag_prefix}-{session.session_id}"
            handler.tag(tag_name, f'Conversion completed for {session.session_id}')
            if self.event_logger:
              self.event_logger.log_event('git_tag', 'Conversion tagged', {'session_id': session.session_id, 'tag': tag_name})
        except Exception as exc:  # pragma: no cover - protective
          if self.event_logger:
            self.event_logger.log_error('git_finalize_failed', {'session_id': session.session_id, 'error': str(exc)})

    self.incremental_cache.prune_missing(
      [record.chunk.file_path for record in session.chunks.values() if record.chunk.stage == Stage.CODE]
    )
    try:
        self.incremental_cache.save(settings.incremental_cache_path)
    except Exception as exc:  # pragma: no cover - protective
      if self.event_logger:
        self.event_logger.log_error('incremental_save_failed', {'error': str(exc)})

  def _enqueue_manual_fix(self, session: ConversionSession, record: ChunkRecord, reason: str, note: Optional[str] = None) -> None:
    entry = session.manual_queue.get(record.chunk.chunk_id)
    if not entry:
      entry = ManualFixEntry(
        chunk_id=record.chunk.chunk_id,
        file_path=str(record.chunk.file_path),
        reason=reason,
        notes=[note] if note else []
      )
      session.manual_queue[record.chunk.chunk_id] = entry
    else:
      if note:
        entry.notes.append(note)
    if note is None and reason not in entry.notes:
      entry.notes.append(reason)
    if session.quality_report is None:
      session.quality_report = QualityReport()
    if record.chunk.chunk_id not in session.quality_report.flagged_chunks:
      session.quality_report.flagged_chunks.append(record.chunk.chunk_id)
    session.summary_notes.append(f'Manual fix required for {record.chunk.file_path}: {reason}')
    if self.event_logger:
      self.event_logger.log_event('manual_fix_enqueued', 'Manual intervention required', {
        'session_id': session.session_id,
        'chunk_id': record.chunk.chunk_id,
        'reason': reason
      })
    self.session_store.upsert(session)

  async def _handle_resource_chunk(self, session: ConversionSession, record: ChunkRecord) -> None:
    target_path = self._determine_output_path(session, record.chunk)
    outputs = self.resource_converter.convert(session.direction, record.chunk, target_path)
    savings_total = 0
    savings_percent = 0.0
    if session.conversion_settings.optimize_assets:
      for output in outputs:
        if output.is_file():
          result = self.asset_optimizer.optimize(output)
          if result and result.savings_bytes > 0:
            savings_total += result.savings_bytes
            savings_percent += result.savings_percent
    if savings_total > 0:
      session.summary_notes.append(
        f'Optimized assets for {record.chunk.file_path} (saved {savings_total} bytes)'
      )
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
      vuln_issues = await self.vulnerability_scanner.scan_packages_config(output)
    elif output.suffix == '.swift':
      vuln_issues = await self.vulnerability_scanner.scan_package_swift(output)
    for issue in license_issues + vuln_issues:
      session.summary_notes.append(f'License/security: {issue.message}')
      if session.quality_report is None:
        session.quality_report = QualityReport()
      session.quality_report.issues.append(issue)
      if issue.severity.lower() == 'error':
        record.status = ChunkStatus.FAILED
        self._enqueue_manual_fix(session, record, 'Security issue', issue.message)
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

  async def _handle_test_chunk(self, session: ConversionSession, record: ChunkRecord) -> None:
    chunk = record.chunk
    try:
      source_text = chunk.file_path.read_text(encoding='utf-8')
    except OSError as exc:
      record.status = ChunkStatus.FAILED
      record.last_error = str(exc)
      session.summary_notes.append(f'Unable to read test file {chunk.file_path}: {exc}')
      self._enqueue_manual_fix(session, record, 'Test conversion', str(exc))
      return

    chunk.content = source_text
    try:
      result = await self.orchestrator.convert_test(
        chunk=chunk,
        config=session.orchestrator_config,
        ai_settings=session.ai_settings,
        direction=session.direction
      )
    except ProviderError as exc:
      record.status = ChunkStatus.FAILED
      record.last_error = str(exc)
      session.summary_notes.append(f'Test conversion failed for {chunk.chunk_id}: {exc}')
      self._enqueue_manual_fix(session, record, 'Test conversion failure', str(exc))
      if self.event_logger:
        self.event_logger.log_error('test_conversion_failed', {'session_id': session.session_id, 'chunk_id': chunk.chunk_id, 'error': str(exc)})
      return

    output_text = result['output_text']
    output_path = self._determine_output_path(session, chunk)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(output_text, encoding='utf-8')

    record.raw_output = output_text
    record.status = ChunkStatus.COMPLETED
    record.summary = f'Test converted: {output_path.name}'
    record.output_path = output_path
    record.tokens_used = result.get('tokens_used', 0)
    record.input_tokens = result.get('input_tokens', 0)
    record.output_tokens = result.get('output_tokens', 0)
    record.cost_usd = result.get('cost_usd', 0.0)
    record.ai_model = result.get('model_identifier')
    record.provider_id = result.get('provider_id')
    record.last_error = None

    checksum = calculate_checksum(chunk.file_path)
    chunk.checksum = checksum
    self.incremental_cache.update_checksum(chunk.file_path, checksum)

    session.summary_notes.append(record.summary)
    session.last_chunk_summary[chunk.file_path.as_posix()] = record.summary
    session.progress.update_chunk(record)

  async def _handle_validation_chunk(self, session: ConversionSession, record: ChunkRecord) -> None:
    issues = await self._run_validation_stage(session)
    record.status = ChunkStatus.COMPLETED
    record.summary = 'Validation completed' if not issues else 'Validation completed with issues'
    session.summary_notes.append(record.summary)
    session.progress.update_chunk(record)

  async def _finalize_tests(self, session: ConversionSession) -> None:
    test_result = await asyncio.to_thread(self.test_harness.run, session)
    if not test_result:
      return
    result = asdict(test_result)
    session.test_results = result
    if result['status'] == 'skipped':
      session.summary_notes.append(f'Tests skipped: {result.get("skipped_reason") or "tooling unavailable"}')
      session.quality_report.issues.append(
        QualityIssue(category='tests', message=result.get('skipped_reason') or 'Tests skipped', severity='info')
      )
      return

    failures = result.get('failures') or []
    summary_line = f"Tests {result['status']}: {len(failures)} failure(s) detected" if failures else f"Tests {result['status']}: 0 failures"
    session.summary_notes.append(summary_line)
    if failures:
      for failure in failures:
        session.quality_report.issues.append(
          QualityIssue(category='tests', message=failure, severity='error')
        )
    else:
      session.quality_report.issues.append(
        QualityIssue(category='tests', message='All automated tests passed', severity='info')
      )
    for todo in result.get('todo') or []:
      session.summary_notes.append(f'TODO: {todo}')

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
      backup_settings=session.backup_settings,
      webhooks=session.webhooks,
      conversion_report=session.conversion_report,
      incremental=session.incremental,
      git_settings=session.git_settings,
      manual_queue=session.manual_queue,
      test_results=session.test_results,
      benchmarks=session.benchmarks
    )
    self.session_store.upsert(state)
    session.last_save = now

  async def _generate_reports(self, session: ConversionSession) -> None:
    from backend.reports.generator import generate_conversion_report

    session.conversion_report = generate_conversion_report(session)
    session.summary_notes.append(f"Quality report generated: {session.conversion_report.summary_html}")

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
