from typing import Dict, Any, Optional, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.api.globals import template_manager, conversion_manager, event_logger, providers
from backend.conversion.models import ConversionSettings, PerformanceSettings, AISettings

router = APIRouter()

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
  use_thinking_mode: bool = Field(default=False) # New field for thinking mode

class TemplatePayload(BaseModel):
  name: str
  conversion: ConversionSettingsPayload
  performance: PerformanceSettingsPayload
  ai: AISettingsPayload
  description: Optional[str] = Field(default='')
  owner: Optional[str] = Field(default='local')
  tags: Optional[List[str]] = Field(default=None)

class TemplateSharePayload(BaseModel):
  name: str
  description: Optional[str] = Field(default='')
  owner: Optional[str] = Field(default='community')
  tags: Optional[List[str]] = Field(default=None)

class DebugTogglePayload(BaseModel):
  enabled: bool

@router.get('/ai/models')
async def ai_models() -> Dict[str, Any]:
  return {'providers': providers.list_providers()}

@router.get('/settings/templates')
async def list_templates(name: Optional[str] = None) -> Dict[str, Any]:
  if name:
    try:
      template = template_manager.load_template(name)
      return {'name': name, 'template': template}
    except FileNotFoundError:
      raise HTTPException(status_code=404, detail='Template not found')
  return template_manager.list_templates()

@router.post('/settings/templates')
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

@router.post('/settings/templates/share')
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

@router.delete('/settings/templates/{name}')
async def delete_template(name: str) -> Dict[str, Any]:
  template_manager.delete_template(name)
  return {'status': 'deleted', 'name': name}

@router.post('/settings/debug')
async def set_debug(payload: DebugTogglePayload) -> Dict[str, Any]:
  conversion_manager.set_debug_mode(payload.enabled)
  event_logger.log_event('debug_toggle', 'Debug mode updated', {'enabled': payload.enabled})
  return {'enabled': payload.enabled}
