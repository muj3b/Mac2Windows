from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Optional

from backend.ai.clients import (
  BaseLLMClient,
  ClaudeClient,
  OpenAIClient,
  OllamaClient,
  ProviderError,
  ProviderResult
)
from backend.ai.prompts import build_conversion_prompt, infer_target_language
from backend.conversion.mappings import ApiMappingCatalog, DependencyMapping
from backend.conversion.models import ChunkWorkItem, AISettings
from backend.ai.model_router import ModelRouter, ModelRoute

logger = logging.getLogger(__name__)


@dataclass
class OrchestrationConfig:
  provider_id: str
  model_identifier: str
  api_key: Optional[str] = None
  temperature: float = 0.1
  max_tokens: int = 4096


class AIOrchestrator:
  """High-level interface responsible for prompt building, model routing, and provider execution."""

  def __init__(
    self,
    provider_registry,
    dependency_mapping: DependencyMapping,
    api_mapping: ApiMappingCatalog,
    model_router: ModelRouter
  ) -> None:
    self.provider_registry = provider_registry
    self.dependency_mapping = dependency_mapping
    self.api_mapping = api_mapping
    self.model_router = model_router
    self._clients: Dict[str, BaseLLMClient] = {}

  async def convert_chunk(
    self,
    chunk: ChunkWorkItem,
    config: OrchestrationConfig,
    ai_settings: AISettings,
    direction: str,
    rag_context: List[Dict[str, str]],
    previous_summary: Optional[str],
    learning_hints: Optional[List[str]] = None
  ) -> Dict[str, object]:
    """Executes conversion with retries, anti-phase enforcement, and contextual prompting."""
    logger.debug(
      'Converting chunk %s direction=%s provider=%s',
      chunk.chunk_id,
      direction,
      config.provider_id
    )

    route = self.model_router.route(chunk, ai_settings, config.provider_id, config.model_identifier)
    prompt_metadata = self._prompt_metadata(chunk, direction, rag_context, previous_summary, learning_hints)
    prompt = self._build_prompt(chunk, direction, rag_context, previous_summary, learning_hints)

    attempt = 0
    cumulative_cost = 0.0
    cumulative_tokens = 0
    provider_result: Optional[ProviderResult] = None
    stopped_early = False
    last_error: Optional[str] = None

    while attempt < ai_settings.retries:
      attempt += 1
      provider_result = await self._invoke_model(
        route=route,
        prompt=prompt,
        temperature=ai_settings.temperature,
        max_tokens=config.max_tokens
      )
      cumulative_cost += provider_result.cost_usd
      cumulative_tokens += provider_result.total_tokens
      output_text = provider_result.output_text
      if self._is_output_complete(output_text):
        break
      if attempt < ai_settings.retries:
        logger.info('Detected incomplete output for %s, reissuing prompt (attempt %s)', chunk.chunk_id, attempt + 1)
        prompt = self._continue_prompt(output_text)
      else:
        stopped_early = True
        last_error = 'Model failed to complete output after retries.'
        break

    if not provider_result:
      raise ProviderError(f'No response returned for chunk {chunk.chunk_id}')

    normalized_output = self._normalize_output(provider_result.output_text, direction, chunk)
    provider_result.output_text = normalized_output
    summary = self._summarize_output(chunk, normalized_output)

    return {
      'output_text': provider_result.output_text,
      'summary': summary,
      'tokens_used': cumulative_tokens or provider_result.total_tokens,
      'input_tokens': provider_result.input_tokens,
      'output_tokens': provider_result.output_tokens,
      'cost_usd': round(cumulative_cost or provider_result.cost_usd, 6),
      'stopped_early': stopped_early,
      'last_error': last_error,
      'raw_response': provider_result.raw_response,
      'prompt_metadata': prompt_metadata,
      'model_identifier': route.model_identifier,
      'provider_id': route.provider_id
    }

  def _prompt_metadata(
    self,
    chunk: ChunkWorkItem,
    direction: str,
    rag_context: List[Dict[str, str]],
    previous_summary: Optional[str],
    learning_hints: Optional[List[str]]
  ) -> Dict[str, object]:
    return {
      'chunk_id': chunk.chunk_id,
      'file_path': str(chunk.file_path),
      'direction': direction,
      'symbols': chunk.symbols,
      'context_documents': [ctx['summary'] for ctx in rag_context],
      'previous_summary': previous_summary,
      'dependency_hints': self.dependency_mapping.directional_map(direction),
      'api_mappings': self.api_mapping.directional_map(direction),
      'learning_hints': learning_hints or []
    }

  def _build_prompt(
    self,
    chunk: ChunkWorkItem,
    direction: str,
    rag_context: List[Dict[str, str]],
    previous_summary: Optional[str],
    learning_hints: Optional[List[str]]
  ) -> str:
    context_summaries = [ctx.get('summary') or ctx.get('document') or '' for ctx in rag_context[:10]]
    dependency_map = self.dependency_mapping.directional_map(direction)
    api_map = self.api_mapping.directional_map(direction)
    return build_conversion_prompt(
      direction=direction,
      chunk=chunk,
      dependency_map=dependency_map,
      api_map=api_map,
      context_summaries=context_summaries,
      learning_hints=learning_hints,
      previous_summary=previous_summary
    )

  async def _invoke_model(
    self,
    route: ModelRoute,
    prompt: str,
    temperature: float,
    max_tokens: int
  ) -> ProviderResult:
    client = self._get_client(route.provider_id)
    return await client.complete(
      model=route.model_identifier,
      prompt=prompt,
      temperature=temperature,
      max_output_tokens=max_tokens,
      stream=True
    )

  def _is_output_complete(self, output: str) -> bool:
    if not output.strip():
      return False
    open_braces = output.count('{')
    close_braces = output.count('}')
    if close_braces and open_braces != close_braces:
      return False
    if output.strip().endswith(('...', 'TODO', 'To be continued')):
      return False
    return True

  def _continue_prompt(self, partial_output: str) -> str:
    return (
      "Continue from exactly where you stopped. Do not repeat previous lines. "
      "Complete the remaining code so the file is fully converted.\n\n"
      f"<partial_output>\n{partial_output}\n</partial_output>"
    )

  def _get_client(self, provider_id: str) -> BaseLLMClient:
    if provider_id in self._clients:
      return self._clients[provider_id]
    if provider_id.startswith('claude'):
      client = ClaudeClient()
    elif provider_id.startswith('gpt-5') or provider_id == 'openai-compatible':
      client = OpenAIClient()
    elif provider_id == 'ollama':
      client = OllamaClient()
    else:
      raise ProviderError(f'Unsupported provider: {provider_id}')
    self._clients[provider_id] = client
    return client

  def _summarize_output(self, chunk: ChunkWorkItem, output_text: str) -> str:
    lines = output_text.splitlines()
    preview = '\n'.join(lines[:4])
    return f'Chunk {chunk.chunk_id} converted ({len(lines)} lines).\n{preview}'

  def _normalize_output(self, text: str, direction: str, chunk: ChunkWorkItem) -> str:
    if not text:
      return ''
    cleaned = text.strip()
    pattern = re.compile(r"```[a-zA-Z0-9_\-]*\n([\s\S]*?)```", re.MULTILINE)
    matches = pattern.findall(cleaned)
    if matches:
      cleaned = matches[0].strip()
    else:
      fence_index = cleaned.find('```')
      if fence_index != -1:
        cleaned = cleaned[fence_index + 3:]
    target_language = infer_target_language(direction, chunk.language or '')
    header = f'// {target_language} conversion'
    if cleaned.startswith(header):
      cleaned = cleaned[len(header):].lstrip()
    return cleaned.strip()

  async def close(self) -> None:
    for client in self._clients.values():
      close = getattr(client, 'aclose', None)
      if close:
        try:
          await close()
        except Exception:  # pragma: no cover - driver shutdown
          logger.debug('Failed to close client cleanly', exc_info=True)
