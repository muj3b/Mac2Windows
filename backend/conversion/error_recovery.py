from __future__ import annotations

import asyncio
import logging
from dataclasses import replace
from typing import Optional

from backend.ai.orchestrator import OrchestrationConfig
from backend.ai.clients import ProviderError
from backend.conversion.models import AISettings, CostSettings

logger = logging.getLogger(__name__)


class ErrorRecoveryEngine:
  """Centralises retry and fallback logic for resilient conversions."""

  def __init__(self, event_logger=None) -> None:
    self._event_logger = event_logger

  async def execute(
    self,
    convert_callable,
    session_id: str,
    chunk_id: str,
    ai_settings: AISettings,
    cost_settings: CostSettings,
    base_config: OrchestrationConfig
  ):
    attempt = 0
    backoff = 1.5
    config = base_config
    fallback_applied = False

    max_attempts = max(ai_settings.retries, 1) + 1  # allow one extra attempt before fallback

    while attempt < max_attempts:
      attempt += 1
      try:
        return await convert_callable(config)
      except ProviderError as exc:
        logger.warning(
          'Provider error for session=%s chunk=%s attempt=%s: %s',
          session_id,
          chunk_id,
          attempt,
          exc
        )
        if self._event_logger:
          self._event_logger.log_error(
            'provider_retry',
            {
              'session_id': session_id,
              'chunk_id': chunk_id,
              'attempt': attempt,
              'error': str(exc)
            }
          )
        await asyncio.sleep(backoff * attempt)

    # attempt fallback if available
    fallback_config = self._resolve_fallback_config(ai_settings, cost_settings, base_config)
    if fallback_config:
      logger.info(
        'Switching to fallback model for session=%s chunk=%s provider=%s model=%s',
        session_id,
        chunk_id,
        fallback_config.provider_id,
        fallback_config.model_identifier
      )
      fallback_applied = True
      try:
        return await convert_callable(fallback_config)
      except ProviderError as exc:
        if self._event_logger:
          self._event_logger.log_error(
            'provider_fallback_failed',
            {
              'session_id': session_id,
              'chunk_id': chunk_id,
              'error': str(exc)
            }
          )
        raise
    if fallback_applied:
      raise ProviderError(f'Fallback model failed for chunk {chunk_id}')
    raise ProviderError(f'Conversion failed for chunk {chunk_id} after retries')

  def _resolve_fallback_config(
    self,
    ai_settings: AISettings,
    cost_settings: CostSettings,
    base_config: OrchestrationConfig
  ) -> Optional[OrchestrationConfig]:
    provider_id = (
      ai_settings.fallback_provider_id
      or cost_settings.fallback_provider_id
      or base_config.provider_id
    )
    model_identifier = (
      ai_settings.fallback_model_identifier
      or cost_settings.fallback_model_identifier
      or base_config.model_identifier
    )
    if provider_id == base_config.provider_id and model_identifier == base_config.model_identifier:
      return None
    return replace(base_config, provider_id=provider_id, model_identifier=model_identifier)
