from typing import Dict, Any, Optional, List

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from backend.api.globals import backup_manager, credential_store, settings

router = APIRouter()

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

@router.get('/backups/providers')
async def list_backup_providers() -> Dict[str, Any]:
  return {'providers': backup_manager.list_providers()}

@router.post('/backups/providers/{provider}/oauth/start')
async def start_backup_oauth(provider: str, payload: BackupOAuthStartPayload) -> Dict[str, Any]:
  try:
    redirect_uri = f'http://{settings.backend_host}:{settings.backend_port}/backups/oauth/{provider}/callback'
    result = backup_manager.start_oauth(provider, payload.dict(exclude_none=True), redirect_uri)
  except ValueError as exc:
    raise HTTPException(status_code=400, detail=str(exc)) from exc
  return result

@router.get('/backups/oauth/{provider}/callback', response_class=HTMLResponse)
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

@router.post('/backups/providers/{provider}/credentials')
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

@router.delete('/backups/credentials/{credential_id}')
async def delete_backup_credential(credential_id: str) -> Dict[str, Any]:
  if not backup_manager.delete_credential(credential_id):
    raise HTTPException(status_code=404, detail='Credential not found')
  return {'status': 'deleted', 'credential_id': credential_id}

@router.get('/backups/sessions/{session_id}')
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
