from typing import Dict, Any, Optional, List
import time
import json

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.api.globals import conversion_manager, event_logger, settings

router = APIRouter()

class IssueReportPayload(BaseModel):
  description: str
  session_id: Optional[str] = None
  include_logs: bool = Field(default=False)
  email: Optional[str] = None

class WebhookConfigPayload(BaseModel):
  url: str
  headers: Optional[Dict[str, str]] = None
  events: Optional[List[str]] = None
  secret_token: Optional[str] = None

class WebhookTestPayload(BaseModel):
  webhooks: List[WebhookConfigPayload]

@router.get('/community/metrics')
async def community_metrics() -> Dict[str, Any]:
  stats = conversion_manager.session_store.statistics()
  return {
    'stats': stats,
    'active_sessions': conversion_manager.active_sessions()
  }

@router.post('/community/report')
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
    # Note: _serialize_summary is not available here directly.
    # We might need to move _serialize_summary to a shared utility or duplicate it.
    # For now, let's assume we can import it or implement a simple version.
    # Ideally, the manager should return a serializable object or we use Pydantic models.
    # To avoid circular imports or complexity, let's just dump the summary object if possible,
    # or we need to bring _serialize_summary to a util.
    # Let's create a util file for serialization.
    pass 
    
  report_path.write_text(json.dumps(content, indent=2), encoding='utf-8')
  return {'report_path': str(report_path)}

@router.post('/conversion/webhook/test')
async def test_webhooks(payload: WebhookTestPayload) -> Dict[str, Any]:
  results = await conversion_manager.test_webhooks([entry.dict() for entry in payload.webhooks])
  return {'results': results}
