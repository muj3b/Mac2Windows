from __future__ import annotations

import asyncio
import json
import math
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import httpx

from backend.config import settings


class ProviderError(RuntimeError):
  """Represents a provider specific failure."""


@dataclass
class ProviderResult:
  output_text: str
  input_tokens: int
  output_tokens: int
  total_tokens: int
  cost_usd: float
  raw_response: Dict[str, object]


def _default_token_estimate(text: str) -> int:
  # Rough heuristic: 1 token ≈ 4 characters
  return max(1, math.ceil(len(text) / 4))


class BaseLLMClient:
  def __init__(self) -> None:
    self.timeout = settings.request_timeout_seconds
    self.max_attempts = max(1, settings.ai_retry_attempts)
    self.backoff = max(0.1, settings.ai_retry_backoff_seconds)

  async def complete(
    self,
    model: str,
    prompt: str,
    temperature: float,
    max_output_tokens: int,
    stream: bool = True
  ) -> ProviderResult:
    raise NotImplementedError


class ClaudeClient(BaseLLMClient):
  PRICE_TABLE = {
    'claude-sonnet-4.5': {'input': 0.003, 'output': 0.015},  # per 1K tokens
    'claude-opus-4.1': {'input': 0.01, 'output': 0.03},
    'claude-sonnet-4': {'input': 0.003, 'output': 0.006}
  }

  def __init__(self) -> None:
    super().__init__()
    if not settings.anthropic_api_key:
      raise ProviderError('ANTHROPIC_API_KEY is not configured.')
    self.base_url = settings.anthropic_api_url.rstrip('/')
    self.headers = {
      'x-api-key': settings.anthropic_api_key,
      'anthropic-version': '2023-06-01',
      'content-type': 'application/json'
    }
    self._client = httpx.AsyncClient(timeout=self.timeout)

  async def complete(
    self,
    model: str,
    prompt: str,
    temperature: float,
    max_output_tokens: int,
    stream: bool = True
  ) -> ProviderResult:
    payload = {
      'model': model,
      'max_tokens': max_output_tokens,
      'temperature': temperature,
      'messages': [{'role': 'user', 'content': [{'type': 'text', 'text': prompt}]}],
      'stream': stream
    }
    endpoint = f'{self.base_url}/v1/messages'
    attempt = 0
    last_error: Optional[Exception] = None

    while attempt < self.max_attempts:
      attempt += 1
      try:
        if stream:
          text, usage = await self._streaming_request(endpoint, payload)
        else:
          text, usage = await self._standard_request(endpoint, payload)
        return self._build_result(text, usage, model, prompt)
      except httpx.HTTPStatusError as exc:
        if exc.response.status_code in {429, 500, 502, 503, 504} and attempt < self.max_attempts:
          await asyncio.sleep(self.backoff * attempt)
          last_error = exc
          continue
        raise ProviderError(f'Claude API error: {exc.response.text}') from exc
      except Exception as exc:  # pragma: no cover - network error fallback
        last_error = exc
        await asyncio.sleep(self.backoff * attempt)
    raise ProviderError(f'Claude request failed after {self.max_attempts} attempts: {last_error}')  # pragma: no cover

  async def _streaming_request(self, endpoint: str, payload: Dict[str, object]) -> Tuple[str, Dict[str, int]]:
    text_fragments: List[str] = []
    usage: Dict[str, int] = {}
    async with self._client.stream('POST', endpoint, headers=self.headers, json=payload) as response:
      response.raise_for_status()
      async for line in response.aiter_lines():
        if not line or not line.startswith('data:'):
          continue
        raw = line[len('data:'):].strip()
        if raw == '[DONE]':
          break
        data = json.loads(raw)
        if data.get('type') == 'message_start':
          continue
        if data.get('type') == 'content_block_delta':
          delta = data.get('delta', {})
          if delta.get('type') == 'text_delta':
            text_fragments.append(delta.get('text', ''))
        if data.get('type') == 'message_delta':
          usage = data.get('usage', usage)
    return ''.join(text_fragments), usage

  async def _standard_request(self, endpoint: str, payload: Dict[str, object]) -> Tuple[str, Dict[str, int]]:
    resp = await self._client.post(endpoint, headers=self.headers, json=payload)
    resp.raise_for_status()
    data = resp.json()
    content = ''.join(block.get('text', '') for block in data.get('content', []) if block.get('type') == 'text')
    usage = data.get('usage', {})
    return content, usage

  def _build_result(self, text: str, usage: Dict[str, int], model: str, prompt: str) -> ProviderResult:
    input_tokens = usage.get('input_tokens') or _default_token_estimate(prompt)
    output_tokens = usage.get('output_tokens') or _default_token_estimate(text)
    pricing = self.PRICE_TABLE.get(model, self.PRICE_TABLE['claude-sonnet-4'])
    cost = ((input_tokens / 1000) * pricing['input']) + ((output_tokens / 1000) * pricing['output'])
    return ProviderResult(
      output_text=text,
      input_tokens=input_tokens,
      output_tokens=output_tokens,
      total_tokens=input_tokens + output_tokens,
      cost_usd=round(cost, 6),
      raw_response={'usage': usage}
    )

  async def aclose(self) -> None:
    await self._client.aclose()


class OpenAIClient(BaseLLMClient):
  PRICE_TABLE = {
    'gpt-5': {'input': 0.01, 'output': 0.03},
    'gpt-5-mini': {'input': 0.003, 'output': 0.006},
    'gpt-5-nano': {'input': 0.0015, 'output': 0.003}
  }

  def __init__(self) -> None:
    super().__init__()
    if not settings.openai_api_key:
      raise ProviderError('OPENAI_API_KEY is not configured.')
    self.base_url = settings.openai_base_url.rstrip('/')
    self.headers = {
      'Authorization': f'Bearer {settings.openai_api_key}',
      'Content-Type': 'application/json'
    }
    if settings.openai_organization:
      self.headers['OpenAI-Organization'] = settings.openai_organization
    self._client = httpx.AsyncClient(timeout=self.timeout)

  async def complete(
    self,
    model: str,
    prompt: str,
    temperature: float,
    max_output_tokens: int,
    stream: bool = True
  ) -> ProviderResult:
    payload = {
      'model': model,
      'temperature': temperature,
      'max_tokens': max_output_tokens,
      'stream': stream,
      'messages': [{'role': 'user', 'content': prompt}]
    }
    endpoint = f'{self.base_url}/chat/completions'
    attempt = 0
    last_error: Optional[Exception] = None

    while attempt < self.max_attempts:
      attempt += 1
      try:
        if stream:
          text, usage = await self._streaming_request(endpoint, payload)
        else:
          text, usage = await self._standard_request(endpoint, payload)
        return self._build_result(text, usage, model, prompt)
      except httpx.HTTPStatusError as exc:
        if exc.response.status_code in {429, 500, 502, 503, 504} and attempt < self.max_attempts:
          await asyncio.sleep(self.backoff * attempt)
          last_error = exc
          continue
        raise ProviderError(f'OpenAI API error: {exc.response.text}') from exc
      except Exception as exc:  # pragma: no cover
        last_error = exc
        await asyncio.sleep(self.backoff * attempt)
    raise ProviderError(f'OpenAI request failed after {self.max_attempts} attempts: {last_error}')  # pragma: no cover

  async def _streaming_request(self, endpoint: str, payload: Dict[str, object]) -> Tuple[str, Dict[str, int]]:
    text_fragments: List[str] = []
    usage: Dict[str, int] = {}
    async with self._client.stream('POST', endpoint, headers=self.headers, json=payload) as response:
      response.raise_for_status()
      async for line in response.aiter_lines():
        if not line or not line.startswith('data:'):
          continue
        raw = line[len('data:'):].strip()
        if raw == '[DONE]':
          break
        data = json.loads(raw)
        choices = data.get('choices', [])
        if choices:
          delta = choices[0].get('delta', {})
          text_fragments.append(delta.get('content', ''))
          if choices[0].get('finish_reason'):
            usage = data.get('usage', usage)
    return ''.join(text_fragments), usage

  async def _standard_request(self, endpoint: str, payload: Dict[str, object]) -> Tuple[str, Dict[str, int]]:
    resp = await self._client.post(endpoint, headers=self.headers, json=payload)
    resp.raise_for_status()
    data = resp.json()
    text = ''.join(choice['message']['content'] for choice in data.get('choices', []) if choice.get('message'))
    usage = data.get('usage', {})
    return text, usage

  def _build_result(self, text: str, usage: Dict[str, int], model: str, prompt: str) -> ProviderResult:
    input_tokens = usage.get('prompt_tokens') or _default_token_estimate(prompt)
    output_tokens = usage.get('completion_tokens') or _default_token_estimate(text)
    pricing = self.PRICE_TABLE.get(model, self.PRICE_TABLE['gpt-5-mini'])
    cost = ((input_tokens / 1000) * pricing['input']) + ((output_tokens / 1000) * pricing['output'])
    return ProviderResult(
      output_text=text,
      input_tokens=input_tokens,
      output_tokens=output_tokens,
      total_tokens=input_tokens + output_tokens,
      cost_usd=round(cost, 6),
      raw_response={'usage': usage}
    )

  async def aclose(self) -> None:
    await self._client.aclose()


class OllamaClient(BaseLLMClient):
  def __init__(self) -> None:
    super().__init__()
    self.base_url = settings.ollama_base_url.rstrip('/')
    self._client = httpx.AsyncClient(timeout=self.timeout)

  async def complete(
    self,
    model: str,
    prompt: str,
    temperature: float,
    max_output_tokens: int,
    stream: bool = True
  ) -> ProviderResult:
    payload = {
      'model': model,
      'prompt': prompt,
      'stream': stream,
      'options': {
        'temperature': temperature,
        'num_predict': max_output_tokens
      }
    }
    endpoint = f'{self.base_url}/api/generate'
    attempt = 0
    last_error: Optional[Exception] = None

    while attempt < self.max_attempts:
      attempt += 1
      try:
        if stream:
          text, usage = await self._streaming_request(endpoint, payload)
        else:
          text, usage = await self._standard_request(endpoint, payload)
        return self._build_result(text, usage, prompt)
      except httpx.HTTPStatusError as exc:
        if exc.response.status_code in {429, 500, 502, 503, 504} and attempt < self.max_attempts:
          await asyncio.sleep(self.backoff * attempt)
          last_error = exc
          continue
        raise ProviderError(f'Ollama API error: {exc.response.text}') from exc
      except Exception as exc:  # pragma: no cover
        last_error = exc
        await asyncio.sleep(self.backoff * attempt)
    raise ProviderError(f'Ollama request failed after {self.max_attempts} attempts: {last_error}')  # pragma: no cover

  async def _streaming_request(self, endpoint: str, payload: Dict[str, object]) -> Tuple[str, Dict[str, int]]:
    text_fragments: List[str] = []
    tokens = 0
    async with self._client.stream('POST', endpoint, json=payload) as response:
      response.raise_for_status()
      async for line in response.aiter_lines():
        if not line:
          continue
        data = json.loads(line)
        if 'response' in data:
          text_fragments.append(data['response'])
        if data.get('done'):
          tokens = data.get('eval_count', tokens)
          break
    usage = {'completion_tokens': tokens, 'prompt_tokens': _default_token_estimate(payload['prompt'])}
    return ''.join(text_fragments), usage

  async def _standard_request(self, endpoint: str, payload: Dict[str, object]) -> Tuple[str, Dict[str, int]]:
    resp = await self._client.post(endpoint, json=payload)
    resp.raise_for_status()
    data = resp.json()
    text = data.get('response', '')
    usage = {
      'completion_tokens': data.get('eval_count', _default_token_estimate(text)),
      'prompt_tokens': data.get('prompt_eval_count', _default_token_estimate(payload['prompt']))
    }
    return text, usage

  def _build_result(self, text: str, usage: Dict[str, int], prompt: str) -> ProviderResult:
    input_tokens = usage.get('prompt_tokens') or _default_token_estimate(prompt)
    output_tokens = usage.get('completion_tokens') or _default_token_estimate(text)
    # Ollama executes local models; we don't attribute per-token cost.
    cost = 0.0
    return ProviderResult(
      output_text=text,
      input_tokens=input_tokens,
      output_tokens=output_tokens,
      total_tokens=input_tokens + output_tokens,
      cost_usd=cost,
      raw_response={'usage': usage}
    )

  async def aclose(self) -> None:
    await self._client.aclose()
