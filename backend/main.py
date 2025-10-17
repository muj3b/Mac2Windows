from __future__ import annotations

import asyncio
import argparse
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional, List

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.ai.clients import ProviderError
from backend.ai.provider_registry import ProviderRegistry
from backend.conversion.manager import ConversionManager
from backend.conversion.mappings import (
  DEPENDENCY_MAP,
  API_MAP,
  DependencyMapping,
  ApiMappingCatalog
)
from backend.conversion.models import ConversionSettings, PerformanceSettings, AISettings, GitSettings, BackupSettings, CostSettings
from backend.config import settings
from backend.detection.scanner import ProjectScanner, ScannerError
from backend.resources.monitor import ResourceMonitor
from backend.storage.embeddings import EmbeddingStore
from backend.storage.state_store import StateStore
from backend.conversion.session_store import ConversionSessionStore
from backend.logging.event_logger import EventLogger
from backend.learning.memory import LearningMemory
from backend.templates.manager import TemplateManager
from backend.batch.manager import BatchManager, BatchItem
from backend.security.secret_manager import SecretManager
from backend.storage.credentials import CredentialStore
from backend.storage.backup import BackupManager

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
logger = logging.getLogger(__name__)

app = FastAPI(
  title='Mac ↔ Windows Universal Converter Backend',
  version='0.1.0',
  description='Provides project detection, AI provider discovery, and resource monitoring services.'
)

app.add_middleware(
  CORSMiddleware,
  allow_origins=['*'],
  allow_credentials=True,
  allow_methods=['*'],
  allow_headers=['*']
)

providers = ProviderRegistry()
scanner = ProjectScanner(settings=settings)
resources = ResourceMonitor()
state_store = StateStore(settings.db_path)
embedding_store = EmbeddingStore(settings.chroma_path)
session_store = ConversionSessionStore(settings.db_path)
event_logger = EventLogger(settings.data_dir / 'logs')
learning_memory = LearningMemory(settings.data_dir / 'learning_memory.json')
template_manager = TemplateManager(settings.data_dir / 'templates')
batch_manager = BatchManager()
secret_manager = SecretManager(settings.secret_key_path)
credential_store = CredentialStore(settings.credentials_db_path, secret_manager)
backup_manager = BackupManager(credential_store, settings.backup_root)
conversion_manager = ConversionManager(
  provider_registry=providers,
  dependency_mapping=DependencyMapping(DEPENDENCY_MAP),
  api_mapping=ApiMappingCatalog(API_MAP),
  embedding_store=embedding_store,
  session_store=session_store,
  resource_monitor=resources,
  backup_manager=backup_manager,
  event_logger=event_logger,
  learning_memory=learning_memory
)


class DetectPayload(BaseModel):
  project_path: str = Field(..., description='Absolute path to the project root directory.')
  direction: Optional[str] = Field(
    default=None,
    description='Conversion direction. Accepts "mac-to-win" or "win-to-mac".'
  )


class ConversionSettingsPayload(BaseModel):
  code_style: str = Field(default='native')
  comments: str = Field(default='keep')
  naming: str = Field(default='preserve')
  error_handling: str = Field(default='adapt')
  cleanup_unused_assets: bool = Field(default=True)
  cleanup_auto_delete: bool = Field(default=False)
  cleanup_min_bytes: int = Field(default=1048576, ge=0)
  preview_mode: bool = Field(default=False)
  exclusions: Optional[List[str]] = Field(default=None)
  quality_score_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
  project_type: Optional[str] = Field(default=None)
  enable_learning: bool = Field(default=True)
  learning_trigger_count: int = Field(default=3, ge=1, le=10)


class PerformanceSettingsPayload(BaseModel):
  max_cpu: int = Field(default=80, ge=40, le=100)
  max_ram_gb: int = Field(default=16, ge=2, le=64)
  threads: int = Field(default=4, ge=1, le=16)
  api_rate_limit: int = Field(default=30, ge=5, le=120)
  parallel_conversions: int = Field(default=1, ge=1, le=4)
  build_timeout_seconds: int = Field(default=600, ge=60, le=3600)
  prefer_offline: bool = Field(default=False)


class AISettingsPayload(BaseModel):
  temperature: float = Field(default=0.2, ge=0.0, le=1.0)
  strategy: str = Field(default='balanced')
  retries: int = Field(default=3, ge=1, le=5)
  offline_only: bool = Field(default=False)
  prompt_tone: str = Field(default='pro')
  fallback_model_identifier: Optional[str] = Field(default=None)
  fallback_provider_id: Optional[str] = Field(default=None)
  smart_prompting: bool = Field(default=True)


class WebhookConfigPayload(BaseModel):
  url: str
  headers: Optional[Dict[str, str]] = None
  events: Optional[List[str]] = None
  secret_token: Optional[str] = None


class CostSettingsPayload(BaseModel):
  enabled: bool = Field(default=True)
  max_budget_usd: float = Field(default=50.0, ge=0.0)
  warn_percent: float = Field(default=0.8, ge=0.1, le=1.0)
  auto_switch_model: bool = Field(default=True)
  fallback_model_identifier: Optional[str] = Field(default=None)
  fallback_provider_id: Optional[str] = Field(default=None)


class GitSettingsPayload(BaseModel):
  enabled: Optional[bool] = Field(default=None)
  tag_after_completion: Optional[bool] = Field(default=None)
  tag_prefix: Optional[str] = Field(default=None)
  branch: Optional[str] = Field(default=None)


class BackupSettingsPayload(BaseModel):
  enabled: bool = Field(default=False)
  provider: str = Field(default='local')
  retention_count: int = Field(default=10, ge=1, le=50)
  remote_path: str = Field(default='{project}/{direction}')
  credential_id: Optional[str] = Field(default=None)


class BackupOAuthStartPayload(BaseModel):
  client_id: str
  client_secret: str
  label: str
  scopes: Optional[List[str]] = None
  root_folder: Optional[str] = None
  tenant: Optional[str] = None


class BackupCredentialPayload(BaseModel):
  label: str
  data: Dict[str, Any]


class TemplatePayload(BaseModel):
  name: str
  conversion: ConversionSettingsPayload
  performance: PerformanceSettingsPayload
  ai: AISettingsPayload
  description: Optional[str] = Field(default='')
  owner: Optional[str] = Field(default='local')
  tags: Optional[List[str]] = Field(default=None)


class BatchConversionItem(BaseModel):
  project_path: str
  target_path: str
  direction: str


class BatchConversionPayload(BaseModel):
  projects: List[BatchConversionItem]
  provider_id: str
  model_identifier: str
  api_key: Optional[str] = None
  conversion: Optional[ConversionSettingsPayload] = None
  performance: Optional[PerformanceSettingsPayload] = None
  ai: Optional[AISettingsPayload] = None
  git: Optional[GitSettingsPayload] = None
  incremental: Optional[bool] = None
  backup: Optional[BackupSettingsPayload] = None
  cost: Optional[CostSettingsPayload] = None


class DebugTogglePayload(BaseModel):
  enabled: bool


class RollbackPayload(BaseModel):
  session_id: str
  backup_path: Optional[str] = None


class ManualFixSubmissionPayload(BaseModel):
  code: str
  note: Optional[str] = None
  submitted_by: Optional[str] = None


class PreviewPayload(BaseModel):
  project_path: str
  direction: str
  exclusions: Optional[List[str]] = None
  model_identifier: Optional[str] = None


class ResumeFailedPayload(BaseModel):
  session_id: str
  provider_id: Optional[str] = None
  model_identifier: Optional[str] = None
  api_key: Optional[str] = None


class TemplateSharePayload(BaseModel):
  name: str
  description: Optional[str] = Field(default='')
  owner: Optional[str] = Field(default='community')
  tags: Optional[List[str]] = Field(default=None)


class IssueReportPayload(BaseModel):
  description: str
  session_id: Optional[str] = None
  include_logs: bool = Field(default=False)
  email: Optional[str] = None


class ConversionStartPayload(BaseModel):
  project_path: str = Field(..., description='Source project root directory.')
  target_path: str = Field(..., description='Output directory for converted project.')
  direction: str = Field(..., pattern='^(mac-to-win|win-to-mac)$')
  provider_id: str = Field(..., description='Selected provider identifier.')
  model_identifier: str = Field(..., description='Model name/path/endpoint.')
  api_key: Optional[str] = Field(default=None, description='API key when required.')
  conversion: Optional[ConversionSettingsPayload] = Field(default=None)
  performance: Optional[PerformanceSettingsPayload] = Field(default=None)
  ai: Optional[AISettingsPayload] = Field(default=None)
  webhooks: Optional[List[WebhookConfigPayload]] = Field(default=None)
  incremental: Optional[bool] = Field(default=False)
  git: Optional[GitSettingsPayload] = Field(default=None)
  backup: Optional[BackupSettingsPayload] = Field(default=None)
  cost: Optional[CostSettingsPayload] = Field(default=None)


class DiffExplanationPayload(BaseModel):
  session_id: str
  file_path: str
  line_number: int = Field(default=0, ge=0)
  before_snippet: str = Field(default='')
  after_snippet: str = Field(default='')


class ConversionControlPayload(BaseModel):
  session_id: str


@app.on_event('startup')
async def startup_event() -> None:
  providers.refresh()
  logger.info('Backend started on %s:%s', settings.backend_host, settings.backend_port)


@app.on_event('shutdown')
async def shutdown_event() -> None:
  await conversion_manager.close()


@app.get('/health')
async def health() -> Dict[str, Any]:
  return {
    'status': 'ok',
    'providers': providers.summary(),
    'resources': resources.snapshot(minimal=True),
    'embeddings': embedding_store.basic_status()
  }


@app.get('/ai/models')
async def ai_models() -> Dict[str, Any]:
  return {'providers': providers.list_providers()}


@app.get('/resources')
async def resource_snapshot() -> Dict[str, Any]:
  return resources.snapshot()


@app.post('/detect')
async def detect_project(payload: DetectPayload) -> Dict[str, Any]:
  try:
    result = await scanner.scan(payload.project_path, direction=payload.direction)
  except ScannerError as exc:
    raise HTTPException(status_code=400, detail=str(exc)) from exc

  await asyncio.to_thread(state_store.record_scan, result)
  return result


@app.post('/conversion/preview')
async def conversion_preview(payload: PreviewPayload) -> Dict[str, Any]:
  project_path = Path(payload.project_path).expanduser().resolve()
  if not project_path.exists() or not project_path.is_dir():
    raise HTTPException(status_code=400, detail='Project path does not exist or is not a directory.')
  estimate = conversion_manager.generate_preview(project_path, payload.direction, payload.exclusions or [])
  model_identifier = payload.model_identifier or 'gpt-5'
  estimated_cost = conversion_manager.cost_tracker.estimate_usd(model_identifier, estimate.estimated_tokens)
  preview = estimate.summary()
  preview['estimated_cost_usd'] = estimated_cost
  preview['model_identifier'] = model_identifier
  return {'preview': preview}


@app.post('/conversion/start')
async def conversion_start(payload: ConversionStartPayload) -> Dict[str, Any]:
  project_path = Path(payload.project_path).expanduser().resolve()
  target_path = Path(payload.target_path).expanduser().resolve()
  if not project_path.exists() or not project_path.is_dir():
    raise HTTPException(status_code=400, detail='Project path does not exist or is not a directory.')
  target_path.mkdir(parents=True, exist_ok=True)

  conversion_dict = payload.conversion.dict() if payload.conversion else {}
  exclusions = conversion_dict.get('exclusions') or []
  preview_estimate = None
  if conversion_dict.get('preview_mode'):
    try:
      preview_estimate = conversion_manager.generate_preview(project_path, payload.direction, exclusions)
    except Exception as exc:  # pragma: no cover - preview optional
      logger.warning('Preview estimation failed: %s', exc)
  conversion_dict['exclusions'] = exclusions
  conversion_settings = ConversionSettings(**conversion_dict) if conversion_dict else ConversionSettings()
  performance_settings = PerformanceSettings(**payload.performance.dict()) if payload.performance else PerformanceSettings()
  ai_settings = AISettings(**payload.ai.dict()) if payload.ai else AISettings()
  webhooks = [hook.dict(exclude_none=True) for hook in payload.webhooks] if payload.webhooks else []
  git_settings = GitSettings(
    enabled=payload.git.enabled if payload.git and payload.git.enabled is not None else settings.git_enabled,
    tag_after_completion=payload.git.tag_after_completion if payload.git and payload.git.tag_after_completion is not None else False,
    tag_prefix=payload.git.tag_prefix if payload.git and payload.git.tag_prefix else settings.git_tag_prefix,
    branch=payload.git.branch if payload.git and payload.git.branch else settings.git_branch
  )
  backup_payload = payload.backup
  backup_settings = BackupSettings(
    enabled=backup_payload.enabled if backup_payload else False,
    provider=backup_payload.provider if backup_payload else settings.default_backup_provider,
    retention_count=backup_payload.retention_count if backup_payload else settings.backup_retention_count,
    remote_path=backup_payload.remote_path if backup_payload else settings.backup_remote_template,
    credential_id=backup_payload.credential_id if backup_payload else None
  )
  cost_settings = CostSettings(**payload.cost.dict()) if payload.cost else CostSettings()

  session = conversion_manager.start_session(
    project_path=project_path,
    target_path=target_path,
    direction=payload.direction,
    provider_id=payload.provider_id,
    model_identifier=payload.model_identifier,
    api_key=payload.api_key,
    conversion_settings=conversion_settings,
    performance_settings=performance_settings,
    ai_settings=ai_settings,
    webhooks=webhooks,
    incremental=payload.incremental or False,
    git_settings=git_settings,
    backup_settings=backup_settings,
    cost_settings=cost_settings,
    preview_estimate=preview_estimate
  )

  summary = session.progress.summary()
  return {
    'session_id': session.session_id,
    'summary': _serialize_summary(summary)
  }


@app.post('/conversion/pause')
async def conversion_pause(payload: ConversionControlPayload) -> Dict[str, Any]:
  if not conversion_manager.pause_session(payload.session_id):
    raise HTTPException(status_code=404, detail='Session not found.')
  summary = conversion_manager.get_summary(payload.session_id)
  return {'session_id': payload.session_id, 'summary': _serialize_summary(summary)}


@app.post('/conversion/resume')
async def conversion_resume(payload: ConversionControlPayload) -> Dict[str, Any]:
  if not conversion_manager.resume_session(payload.session_id):
    raise HTTPException(status_code=404, detail='Session not found or completed.')
  summary = conversion_manager.get_summary(payload.session_id)
  return {'session_id': payload.session_id, 'summary': _serialize_summary(summary)}


@app.post('/conversion/resume_failed')
async def conversion_resume_failed(payload: ResumeFailedPayload) -> Dict[str, Any]:
  try:
    session = conversion_manager.resume_failed_session(
      session_id=payload.session_id,
      provider_id=payload.provider_id,
      model_identifier=payload.model_identifier,
      api_key=payload.api_key
    )
  except ValueError as exc:
    raise HTTPException(status_code=400, detail=str(exc)) from exc
  summary = conversion_manager.get_summary(session.session_id)
  return {'session_id': session.session_id, 'summary': _serialize_summary(summary)}


@app.get('/conversion/status/{session_id}')
async def conversion_status(session_id: str) -> Dict[str, Any]:
  summary = conversion_manager.get_summary(session_id)
  if not summary:
    raise HTTPException(status_code=404, detail='Session not found.')
  return {'session_id': session_id, 'summary': _serialize_summary(summary)}


@app.get('/conversion/manual/{session_id}')
async def conversion_manual_list(session_id: str) -> Dict[str, Any]:
  fixes = conversion_manager.list_manual_fixes(session_id)
  return {'manual_fixes': fixes}


@app.post('/conversion/manual/{session_id}/{chunk_id}')
async def conversion_manual_apply(session_id: str, chunk_id: str, payload: ManualFixSubmissionPayload) -> Dict[str, Any]:
  try:
    conversion_manager.submit_manual_fix(session_id, chunk_id, payload.code, submitted_by=payload.submitted_by, note=payload.note)
  except ValueError as exc:  # session not active or chunk missing
    raise HTTPException(status_code=400, detail=str(exc))
  summary = conversion_manager.get_summary(session_id)
  return {
    'session_id': session_id,
    'chunk_id': chunk_id,
    'status': 'applied',
    'summary': _serialize_summary(summary)
  }


def _serialize_summary(summary: Optional[Any]) -> Optional[Dict[str, Any]]:
  if not summary:
    return None
  return {
    'overall_percentage': summary.overall_percentage,
    'tokens_used': summary.tokens_used,
    'cost_usd': summary.cost_usd,
    'elapsed_seconds': summary.elapsed_seconds,
    'estimated_seconds_remaining': summary.estimated_seconds_remaining,
    'converted_files': summary.converted_files,
    'total_files': summary.total_files,
    'paused': summary.paused,
    'direction': summary.direction,
    'current_chunk': _serialize_chunk(summary.current_chunk),
    'stage_progress': {
      stage.name: {
        'completed_units': progress.completed_units,
        'total_units': progress.total_units,
        'status': progress.status,
        'percentage': progress.percentage
      }
      for stage, progress in summary.stage_progress.items()
    },
    'quality_report': summary.quality_report.summary() if summary.quality_report else None,
    'conversion_report': str(summary.conversion_report.summary_html) if summary.conversion_report else None,
    'manual_fixes_pending': summary.manual_fixes_pending,
    'backups': summary.backups,
    'test_results': summary.test_results,
    'benchmarks': summary.benchmarks,
    'cleanup_report': summary.cleanup_report.summary() if summary.cleanup_report else None,
    'quality_score': summary.quality_score,
    'warnings': summary.warnings,
    'cost_settings': summary.cost_settings.__dict__ if summary.cost_settings else None,
    'cost_percent_consumed': summary.cost_percent_consumed,
    'project_type': summary.project_type,
    'offline_mode': summary.offline_mode,
    'preview_estimate': summary.preview_estimate.summary() if summary.preview_estimate else None
  }


def _serialize_chunk(chunk: Optional[Any]) -> Optional[Dict[str, Any]]:
  if not chunk:
    return None
  return {
    'chunk_id': chunk.chunk.chunk_id,
    'file_path': str(chunk.chunk.file_path),
    'stage': chunk.chunk.stage.name,
    'status': chunk.status.name,
    'tokens_used': chunk.tokens_used,
    'cost_usd': chunk.cost_usd,
    'summary': chunk.summary,
    'output_path': str(chunk.output_path) if chunk.output_path else None,
    'model_identifier': chunk.ai_model,
    'provider_id': chunk.provider_id
  }


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description='Backend service for the converter.')
  parser.add_argument('--host', default=settings.backend_host, help='Host interface to bind.')
  parser.add_argument('--port', default=settings.backend_port, type=int, help='Port to serve on.')
  parser.add_argument('--reload', action='store_true', help='Enable autoreload (development only).')
  parser.add_argument('--log-level', default=settings.log_level, help='Uvicorn log level.')
  return parser.parse_args()


def main() -> None:
  args = parse_args()
  uvicorn.run(
    'backend.main:app',
    host=args.host,
    port=args.port,
    log_level=args.log_level,
    reload=args.reload
  )


if __name__ == '__main__':
  main()
@app.get('/settings/templates')
async def list_templates(name: Optional[str] = None) -> Dict[str, Any]:
  if name:
    try:
      template = template_manager.load_template(name)
      return {'name': name, 'template': template}
    except FileNotFoundError:
      raise HTTPException(status_code=404, detail='Template not found')
  return template_manager.list_templates()


@app.post('/settings/templates')
async def save_template(payload: TemplatePayload) -> Dict[str, Any]:
  path = template_manager.save_template(
    name=payload.name,
    conversion=ConversionSettings(**payload.conversion.dict()),
    performance=PerformanceSettings(**payload.performance.dict()),
    ai=AISettings(**payload.ai.dict()),
    description=payload.description or '',
    owner=payload.owner or 'local',
    tags=payload.tags or []
  )
  return {'name': payload.name, 'path': str(path)}


@app.post('/settings/templates/share')
async def share_template(payload: TemplateSharePayload) -> Dict[str, Any]:
  try:
    descriptor = template_manager.share_template(
      name=payload.name,
      description=payload.description or '',
      owner=payload.owner or 'community',
      tags=payload.tags or []
    )
  except FileNotFoundError as exc:
    raise HTTPException(status_code=404, detail=str(exc)) from exc
  return {'template': descriptor}


@app.delete('/settings/templates/{name}')
async def delete_template(name: str) -> Dict[str, Any]:
  template_manager.delete_template(name)
  return {'status': 'deleted', 'name': name}


@app.get('/community/metrics')
async def community_metrics() -> Dict[str, Any]:
  stats = conversion_manager.session_store.statistics()
  return {
    'stats': stats,
    'active_sessions': conversion_manager.active_sessions()
  }


@app.post('/community/report')
async def community_report(payload: IssueReportPayload) -> Dict[str, Any]:
  report_dir = settings.data_dir / 'community' / 'reports'
  report_dir.mkdir(parents=True, exist_ok=True)
  timestamp = int(time.time() * 1000)
  report_path = report_dir / f'report_{timestamp}.json'
  content: Dict[str, Any] = {
    'description': payload.description,
    'session_id': payload.session_id,
    'email': payload.email,
    'created_at': timestamp
  }
  if payload.include_logs:
    content['logs'] = event_logger.recent(200)
  if payload.session_id:
    summary = conversion_manager.get_summary(payload.session_id)
    content['summary'] = _serialize_summary(summary)
  report_path.write_text(json.dumps(content, indent=2), encoding='utf-8')
  return {'report_path': str(report_path)}


@app.get('/logs/recent')
async def recent_logs(limit: int = 200) -> Dict[str, Any]:
  return {'entries': event_logger.recent(limit)}


@app.post('/settings/debug')
async def set_debug(payload: DebugTogglePayload) -> Dict[str, Any]:
  conversion_manager.set_debug_mode(payload.enabled)
  event_logger.log_event('debug_toggle', 'Debug mode updated', {'enabled': payload.enabled})
  return {'enabled': payload.enabled}


@app.get('/backups/providers')
async def list_backup_providers() -> Dict[str, Any]:
  return {'providers': backup_manager.list_providers()}


@app.post('/backups/providers/{provider}/oauth/start')
async def start_backup_oauth(provider: str, payload: BackupOAuthStartPayload) -> Dict[str, Any]:
  try:
    redirect_uri = f'http://{settings.backend_host}:{settings.backend_port}/backups/oauth/{provider}/callback'
    result = backup_manager.start_oauth(provider, payload.dict(exclude_none=True), redirect_uri)
  except ValueError as exc:
    raise HTTPException(status_code=400, detail=str(exc)) from exc
  return result


@app.get('/backups/oauth/{provider}/callback', response_class=HTMLResponse)
async def complete_backup_oauth(
  provider: str,
  state: Optional[str] = None,
  code: Optional[str] = None,
  error: Optional[str] = None,
  error_description: Optional[str] = None
) -> HTMLResponse:
  if error:
    content = f"<html><body><h1>Authorization failed</h1><p>{error_description or error}</p></body></html>"
    return HTMLResponse(content=content, status_code=400)
  if not state or not code:
    raise HTTPException(status_code=400, detail='Missing OAuth code or state parameter.')
  try:
    record = backup_manager.complete_oauth(provider, state, code)
  except ValueError as exc:
    content = f"<html><body><h1>Authorization failed</h1><p>{exc}</p></body></html>"
    return HTMLResponse(content=content, status_code=400)
  content = (
    "<html><body><h1>Backup provider connected</h1>"
    f"<p>Credential saved as: {record.label}</p>"
    "<p>You may close this window.</p>"
    "<script>setTimeout(() => window.close(), 1500);</script>"
    "</body></html>"
  )
  return HTMLResponse(content=content)


@app.post('/backups/providers/{provider}/credentials')
async def create_backup_credentials(provider: str, payload: BackupCredentialPayload) -> Dict[str, Any]:
  try:
    record = credential_store.save_credentials(provider, payload.label, payload.data)
  except ValueError as exc:
    raise HTTPException(status_code=400, detail=str(exc)) from exc
  return {
    'credential': {
      'id': record.id,
      'provider': record.provider,
      'label': record.label,
      'created_at': record.created_at,
      'updated_at': record.updated_at
    }
  }


@app.delete('/backups/credentials/{credential_id}')
async def delete_backup_credential(credential_id: str) -> Dict[str, Any]:
  if not backup_manager.delete_credential(credential_id):
    raise HTTPException(status_code=404, detail='Credential not found')
  return {'status': 'deleted', 'credential_id': credential_id}


@app.get('/backups/sessions/{session_id}')
async def list_session_backups(session_id: str) -> Dict[str, Any]:
  records = backup_manager.list_backups(session_id=session_id)
  return {
    'backups': [
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
  }


@app.post('/diff/explain')
async def explain_diff(payload: DiffExplanationPayload) -> Dict[str, Any]:
  if not payload.before_snippet.strip() and not payload.after_snippet.strip():
    raise HTTPException(status_code=400, detail='Diff snippets required for explanation.')
  session = conversion_manager.sessions.get(payload.session_id)
  if not session:
    raise HTTPException(status_code=404, detail='Session must be active to request diff explanations.')
  metadata = {
    'file_path': payload.file_path,
    'line_number': payload.line_number,
    'direction': session.direction
  }
  try:
    result = await conversion_manager.orchestrator.explain_diff(
      session.orchestrator_config,
      payload.before_snippet,
      payload.after_snippet,
      metadata
    )
  except ProviderError as exc:
    raise HTTPException(status_code=502, detail=str(exc)) from exc
  return result


@app.post('/conversion/rollback')
async def prepare_rollback(payload: RollbackPayload) -> Dict[str, Any]:
  backup_path = Path(payload.backup_path) if payload.backup_path else None
  restore_dir = conversion_manager.rollback(payload.session_id, backup_path)
  return {'restore_directory': str(restore_dir)}


@app.post('/conversion/batch')
async def start_batch(payload: BatchConversionPayload) -> Dict[str, Any]:
  conversion_settings = ConversionSettings(**payload.conversion.dict()) if payload.conversion else ConversionSettings()
  performance_settings = PerformanceSettings(**payload.performance.dict()) if payload.performance else PerformanceSettings()
  ai_settings = AISettings(**payload.ai.dict()) if payload.ai else AISettings()
  git_settings = GitSettings(
    enabled=payload.git.enabled if payload.git and payload.git.enabled is not None else settings.git_enabled,
    tag_after_completion=payload.git.tag_after_completion if payload.git and payload.git.tag_after_completion is not None else False,
    tag_prefix=payload.git.tag_prefix if payload.git and payload.git.tag_prefix else settings.git_tag_prefix,
    branch=payload.git.branch if payload.git and payload.git.branch else settings.git_branch
  )
  backup_payload = payload.backup
  backup_settings = BackupSettings(
    enabled=backup_payload.enabled if backup_payload else False,
    provider=backup_payload.provider if backup_payload else settings.default_backup_provider,
    retention_count=backup_payload.retention_count if backup_payload else settings.backup_retention_count,
    remote_path=backup_payload.remote_path if backup_payload else settings.backup_remote_template,
    credential_id=backup_payload.credential_id if backup_payload else None
  )
  cost_settings = CostSettings(**payload.cost.dict()) if payload.cost else CostSettings()
  scheduled = []
  for project in payload.projects:
    batch_item = BatchItem(
      project_path=Path(project.project_path).expanduser().resolve(),
      target_path=Path(project.target_path).expanduser().resolve(),
      direction=project.direction
    )
    batch_manager.schedule([batch_item])
    session = conversion_manager.start_session(
      project_path=batch_item.project_path,
      target_path=batch_item.target_path,
      direction=batch_item.direction,
      provider_id=payload.provider_id,
      model_identifier=payload.model_identifier,
      api_key=payload.api_key,
      conversion_settings=conversion_settings,
      performance_settings=performance_settings,
      ai_settings=ai_settings,
      webhooks=[],
      incremental=payload.incremental or False,
      git_settings=git_settings,
      backup_settings=backup_settings,
      cost_settings=cost_settings
    )
    scheduled.append(session.session_id)
  return {'scheduled_sessions': scheduled}
