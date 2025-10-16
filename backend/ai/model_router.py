from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from backend.conversion.models import ChunkWorkItem
from backend.conversion.models import AISettings


@dataclass
class ModelRoute:
  provider_id: str
  model_identifier: str


class ModelRouter:
  """Routes conversion chunks to the most appropriate model/endpoint."""

  def __init__(self, provider_registry) -> None:
    self.provider_registry = provider_registry

  def route(
    self,
    chunk: ChunkWorkItem,
    ai_settings: AISettings,
    preferred_provider: str,
    preferred_model: str
  ) -> ModelRoute:
    language = chunk.language.lower()
    size = chunk.end_line - chunk.start_line
    complexity = len(chunk.symbols)

    strategy = ai_settings.strategy

    if strategy == 'cost':
      provider_candidate = preferred_provider
      model_candidate = self._fast_model(preferred_model)
      if not self.provider_registry.is_available(provider_candidate):
        model_candidate = preferred_model
      return ModelRoute(provider_id=provider_candidate, model_identifier=model_candidate)

    if strategy == 'speed':
      provider_candidate = preferred_provider
      model_candidate = self._fast_model(preferred_model)
      if not self.provider_registry.is_available(provider_candidate):
        model_candidate = preferred_model
      return ModelRoute(provider_id=provider_candidate, model_identifier=model_candidate)

    if size > 400 or complexity > 10:
      provider_candidate = 'claude-sonnet-4-5'
      model_candidate = 'claude-sonnet-4.5'
      if not self.provider_registry.is_available(provider_candidate):
        provider_candidate = preferred_provider
        model_candidate = preferred_model
      return ModelRoute(provider_id=provider_candidate, model_identifier=model_candidate)

    if language in {'swift', 'objective-c', 'objective-c++'} and complexity > 5:
      provider_candidate = 'claude-opus-4-1'
      model_candidate = 'claude-opus-4.1'
      if not self.provider_registry.is_available(provider_candidate):
        provider_candidate = preferred_provider
        model_candidate = preferred_model
      return ModelRoute(provider_id=provider_candidate, model_identifier=model_candidate)

    if language in {'c#', 'xaml'} and complexity > 5:
      provider_candidate = 'openai-compatible'
      model_candidate = 'gpt-5'
      if not self.provider_registry.is_available(provider_candidate):
        provider_candidate = preferred_provider
        model_candidate = preferred_model
      return ModelRoute(provider_id=provider_candidate, model_identifier=model_candidate)

    provider_candidate = preferred_provider
    model_candidate = preferred_model
    if not self.provider_registry.is_available(provider_candidate):
      if self.provider_registry.is_available('ollama'):
        provider_candidate = 'ollama'
      else:
        provider_candidate = preferred_provider
    return ModelRoute(provider_id=provider_candidate, model_identifier=model_candidate)

  def _fast_model(self, fallback: str) -> str:
    fast_map = {
      'gpt-5': 'gpt-5-mini',
      'claude-opus-4.1': 'claude-sonnet-4',
      'claude-sonnet-4.5': 'claude-sonnet-4'
    }
    return fast_map.get(fallback, fallback)
