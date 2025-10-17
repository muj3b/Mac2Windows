from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Dict, Iterable, List, Optional

import httpx

from backend.conversion.models import WebhookConfig

logger = logging.getLogger(__name__)


class WebhookDeliveryError(Exception):
  """Raised when a webhook fails after all retry attempts."""


class WebhookManager:
  """Dispatches structured webhook events with retry, backoff, and header customisation."""

  def __init__(
    self,
    timeout_seconds: float = 12.0,
    max_attempts: int = 3,
    backoff_seconds: float = 2.5
  ) -> None:
    self.timeout_seconds = timeout_seconds
    self.max_attempts = max_attempts
    self.backoff_seconds = backoff_seconds

  async def dispatch(
    self,
    targets: Iterable[WebhookConfig],
    event_name: str,
    payload: Dict[str, object]
  ) -> List[Dict[str, object]]:
    results: List[Dict[str, object]] = []
    tasks = [
      self._send_with_retry(config, event_name, payload)
      for config in targets
      if config.should_fire(event_name)
    ]
    if not tasks:
      return results
    responses = await asyncio.gather(*tasks, return_exceptions=True)
    for response in responses:
      if isinstance(response, Exception):
        logger.warning('Webhook dispatch failed: %s', response)
        continue
      results.append(response)
    return results

  async def _send_with_retry(
    self,
    config: WebhookConfig,
    event_name: str,
    payload: Dict[str, object]
  ) -> Dict[str, object]:
    attempt = 0
    headers = {'Content-Type': 'application/json'}
    headers.update({key: value for key, value in config.headers.items() if value is not None})

    signed_payload = payload
    signature: Optional[str] = None
    if config.secret_token:
      import hashlib
      import hmac

      serialized = json.dumps(payload, sort_keys=True).encode('utf-8')
      signature = hmac.new(
        config.secret_token.encode('utf-8'),
        serialized,
        hashlib.sha256
      ).hexdigest()
      headers['X-Webhook-Signature'] = signature
      headers['X-Webhook-Event'] = event_name

    while attempt < self.max_attempts:
      attempt += 1
      try:
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
          response = await client.post(
            config.url,
            json={
              'event': event_name,
              'timestamp': time.time(),
              'payload': signed_payload,
              'attempt': attempt,
              'signature': signature
            },
            headers=headers
          )
          response.raise_for_status()
          logger.debug('Webhook %s delivered (attempt %s)', config.url, attempt)
          return {
            'url': config.url,
            'status': response.status_code,
            'attempts': attempt
          }
      except Exception as exc:  # pragma: no cover - network heavy
        logger.warning(
          'Webhook delivery attempt %s failed for %s: %s',
          attempt,
          config.url,
          exc
        )
        if attempt >= self.max_attempts:
          raise WebhookDeliveryError(f'{config.url} failed after {attempt} attempts') from exc
        await asyncio.sleep(self.backoff_seconds * attempt)
    raise WebhookDeliveryError(f'{config.url} failed unexpectedly')
