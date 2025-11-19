from typing import Dict, Any
import platform
import sys

from fastapi import APIRouter

from backend.api.globals import providers, resources, embedding_store

router = APIRouter()

@router.get('/health')
async def health() -> Dict[str, Any]:
  return {
    'status': 'ok',
    'providers': providers.summary(),
    'resources': resources.snapshot(minimal=True),
    'embeddings': embedding_store.basic_status()
  }

@router.get('/resources')
async def resource_snapshot() -> Dict[str, Any]:
  return resources.snapshot()

@router.get('/system/info')
async def system_info() -> Dict[str, Any]:
  return {
    'os': platform.system(),
    'os_release': platform.release(),
    'os_version': platform.version(),
    'machine': platform.machine(),
    'python_version': sys.version,
    'platform': platform.platform(),
    'processor': platform.processor()
  }
