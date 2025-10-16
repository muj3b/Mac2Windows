from __future__ import annotations

import asyncio
import argparse
import logging
from pathlib import Path
from typing import Any, Dict, Optional, List

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.ai.provider_registry import ProviderRegistry
from backend.conversion.manager import ConversionManager
from backend.conversion.mappings import (
  DEPENDENCY_MAP,
  API_MAP,
  DependencyMapping,
  ApiMappingCatalog
)
from backend.conversion.models import ConversionSettings, PerformanceSettings, AISettings
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
conversion_manager = ConversionManager(
  provider_registry=providers,
  dependency_mapping=DependencyMapping(DEPENDENCY_MAP),
  api_mapping=ApiMappingCatalog(API_MAP),
  embedding_store=embedding_store,
  session_store=session_store,
  resource_monitor=resources,
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


class PerformanceSettingsPayload(BaseModel):
  max_cpu: int = Field(default=80, ge=40, le=100)
  max_ram_gb: int = Field(default=16, ge=2, le=64)
  threads: int = Field(default=4, ge=1, le=16)
  api_rate_limit: int = Field(default=30, ge=5, le=120)


class AISettingsPayload(BaseModel):
  temperature: float = Field(default=0.2, ge=0.0, le=1.0)
  strategy: str = Field(default='balanced')
  retries: int = Field(default=3, ge=1, le=5)


class TemplatePayload(BaseModel):
  name: str
  conversion: ConversionSettingsPayload
  performance: PerformanceSettingsPayload
  ai: AISettingsPayload


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


class DebugTogglePayload(BaseModel):
  enabled: bool


class RollbackPayload(BaseModel):
  session_id: str
  backup_path: Optional[str] = None


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
  webhooks: Optional[List[str]] = Field(default=None)
  incremental: Optional[bool] = Field(default=False)


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


@app.post('/conversion/start')
async def conversion_start(payload: ConversionStartPayload) -> Dict[str, Any]:
  project_path = Path(payload.project_path).expanduser().resolve()
  target_path = Path(payload.target_path).expanduser().resolve()
  if not project_path.exists() or not project_path.is_dir():
    raise HTTPException(status_code=400, detail='Project path does not exist or is not a directory.')
  target_path.mkdir(parents=True, exist_ok=True)

  conversion_settings = ConversionSettings(**payload.conversion.dict()) if payload.conversion else ConversionSettings()
  performance_settings = PerformanceSettings(**payload.performance.dict()) if payload.performance else PerformanceSettings()
  ai_settings = AISettings(**payload.ai.dict()) if payload.ai else AISettings()
  webhooks = payload.webhooks or []

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
    incremental=payload.incremental or False
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


@app.get('/conversion/status/{session_id}')
async def conversion_status(session_id: str) -> Dict[str, Any]:
  summary = conversion_manager.get_summary(session_id)
  if not summary:
    raise HTTPException(status_code=404, detail='Session not found.')
  return {'session_id': session_id, 'summary': _serialize_summary(summary)}


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
    'conversion_report': str(summary.conversion_report.summary_html) if summary.conversion_report else None
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
    ai=AISettings(**payload.ai.dict())
  )
  return {'name': payload.name, 'path': str(path)}


@app.get('/logs/recent')
async def recent_logs(limit: int = 200) -> Dict[str, Any]:
  return {'entries': event_logger.recent(limit)}


@app.post('/settings/debug')
async def set_debug(payload: DebugTogglePayload) -> Dict[str, Any]:
  conversion_manager.set_debug_mode(payload.enabled)
  event_logger.log_event('debug_toggle', 'Debug mode updated', {'enabled': payload.enabled})
  return {'enabled': payload.enabled}


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
      ai_settings=ai_settings
    )
    scheduled.append(session.session_id)
  return {'scheduled_sessions': scheduled}
