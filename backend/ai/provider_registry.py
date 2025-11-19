from __future__ import annotations

import os
import platform
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from backend.config import settings


@dataclass
class Provider:
  id: str
  label: str
  kind: str
  requires_api_key: bool
  default_identifier: Optional[str] = None
  metadata: Dict[str, str] = field(default_factory=dict)
  available: bool = False


class ProviderRegistry:
  """Catalog of supported AI providers with lightweight availability checks."""

  def __init__(self) -> None:
    self.providers: List[Provider] = []
    self.refresh()

  def refresh(self) -> None:
    self.providers = self._base_providers()
    for provider in self.providers:
      provider.available = self._is_provider_available(provider)

  def list_providers(self) -> List[Dict[str, object]]:
    return [self._provider_to_dict(provider) for provider in self.providers]

  def summary(self) -> Dict[str, object]:
    total = len(self.providers)
    available = sum(1 for provider in self.providers if provider.available)
    return {
      'total': total,
      'available': available,
      'unavailable': total - available
    }

  def is_available(self, provider_id: str) -> bool:
    for provider in self.providers:
      if provider.id == provider_id:
        return provider.available
    return False

  def _provider_to_dict(self, provider: Provider) -> Dict[str, object]:
    return {
      'id': provider.id,
      'label': provider.label,
      'type': provider.kind,
      'requires_api_key': provider.requires_api_key,
      'default_identifier': provider.default_identifier,
      'metadata': provider.metadata,
      'available': provider.available
    }

  def _is_provider_available(self, provider: Provider) -> bool:
    if provider.kind == 'cloud':
      if provider.id.startswith('claude'):
        return settings.anthropic_api_key is not None
      if provider.id.startswith('gpt-5'):
        return settings.openai_api_key is not None
      if provider.id.startswith('gpt-5'):
        return settings.openai_api_key is not None
      if provider.id.startswith('gemini'):
        return settings.gemini_api_key is not None
      if provider.id in {'deepseek-v3-2', 'codestral', 'custom-endpoint'}:
        return True
      return True

    detector = {
      'ollama': self._detect_executable('ollama'),
      'lm-studio': self._detect_lm_studio(),
      'llama-cpp': self._detect_llama_cpp(),
      'gpt4all': self._detect_executable('gpt4all'),
      'openai-compatible': self._detect_openai_compat()
    }.get(provider.id)
    return bool(detector)

  def _base_providers(self) -> List[Provider]:
    return [
      Provider(
        id='ollama',
        label='Ollama (local)',
        kind='local',
        requires_api_key=False,
        default_identifier='ollama::llama3'
      ),
      Provider(
        id='lm-studio',
        label='LM Studio (local)',
        kind='local',
        requires_api_key=False,
        default_identifier='lmstudio::ggml'
      ),
      Provider(
        id='llama-cpp',
        label='llama.cpp (GGUF)',
        kind='local',
        requires_api_key=False,
        default_identifier='llamacpp::model.gguf'
      ),
      Provider(
        id='gpt4all',
        label='GPT4All (local)',
        kind='local',
        requires_api_key=False,
        default_identifier='gpt4all::model.bin'
      ),
      Provider(
        id='openai-compatible',
        label='OpenAI-Compatible Endpoint',
        kind='local',
        requires_api_key=True,
        default_identifier='http://127.0.0.1:8080/v1'
      ),
      Provider(
        id='claude-sonnet-4-5',
        label='Claude Sonnet 4.5 (cloud)',
        kind='cloud',
        requires_api_key=True,
        default_identifier='claude-sonnet-4.5'
      ),
      Provider(
        id='claude-opus-4-1',
        label='Claude Opus 4.1 (cloud)',
        kind='cloud',
        requires_api_key=True,
        default_identifier='claude-opus-4.1'
      ),
      Provider(
        id='claude-sonnet-4',
        label='Claude Sonnet 4 (cloud)',
        kind='cloud',
        requires_api_key=True,
        default_identifier='claude-sonnet-4'
      ),
      Provider(
        id='gpt-5',
        label='GPT-5 (cloud)',
        kind='cloud',
        requires_api_key=True,
        default_identifier='gpt-5'
      ),
      Provider(
        id='gpt-5-mini',
        label='GPT-5 Mini (cloud)',
        kind='cloud',
        requires_api_key=True,
        default_identifier='gpt-5-mini'
      ),
      Provider(
        id='gpt-5-nano',
        label='GPT-5 Nano (cloud)',
        kind='cloud',
        requires_api_key=True,
        default_identifier='gpt-5-nano'
      ),
      Provider(
        id='gemini-2-5-pro',
        label='Gemini 2.5 Pro (1M-2M ctx)',
        kind='cloud',
        requires_api_key=True,
        default_identifier='gemini-2.5-pro'
      ),
      Provider(
        id='gemini-flash-2-0',
        label='Gemini Flash 2.0',
        kind='cloud',
        requires_api_key=True,
        default_identifier='gemini-flash-2.0'
      ),
      Provider(
        id='deepseek-v3-2',
        label='DeepSeek V3.2',
        kind='cloud',
        requires_api_key=True,
        default_identifier='deepseek-v3.2'
      ),
      Provider(
        id='codestral',
        label='Codestral',
        kind='cloud',
        requires_api_key=True,
        default_identifier='codestral'
      ),
      Provider(
        id='custom-endpoint',
        label='Custom Endpoint',
        kind='cloud',
        requires_api_key=True,
        default_identifier='https://api.example.com/v1'
      )
    ]

  def _detect_executable(self, name: str) -> bool:
    return shutil.which(name) is not None

  def _detect_lm_studio(self) -> bool:
    # LM Studio typically stores models or configuration in Application Support
    if platform.system() == 'Darwin':
      path = Path.home() / 'Library/Application Support/LM Studio'
    elif platform.system() == 'Windows':
      path = Path(os.getenv('APPDATA', '')) / 'LM Studio'
    else:
      path = Path.home() / '.config/LM Studio'
    return path.exists()

  def _detect_llama_cpp(self) -> bool:
    return any(
      (Path.cwd() / candidate).exists()
      for candidate in ('main', 'main.exe', 'llama.cpp', 'llama-cli')
    ) or shutil.which('llama-cpp') is not None

  def _detect_openai_compat(self) -> bool:
    return bool(os.getenv('OPENAI_BASE_URL') or os.getenv('OPENAI_API_KEY'))
