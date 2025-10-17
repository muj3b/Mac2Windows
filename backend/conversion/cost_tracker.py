from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Optional

from backend.conversion.models import CostSettings

logger = logging.getLogger(__name__)


MODEL_PRICING_PER_1K = {
  'gpt-5': 0.045,
  'gpt-5-mini': 0.018,
  'gpt-5-nano': 0.004,
  'claude-opus-4.1': 0.048,
  'claude-sonnet-4.5': 0.032,
  'claude-sonnet-4': 0.024,
  'ollama::llama3': 0.0,
  'ollama::codellama': 0.0
}


@dataclass
class CostUpdate:
  continue_processing: bool
  total_cost: float
  percent_consumed: float
  warning: Optional[str] = None
  switched_model: bool = False


class CostTracker:
  """Tracks per-session spend and enforces configured budgets."""

  def __init__(self, event_logger=None) -> None:
    self._sessions: Dict[str, Dict[str, float]] = {}
    self._event_logger = event_logger

  def start(self, session_id: str, cost_settings: CostSettings) -> None:
    self._sessions[session_id] = {
      'total_cost': 0.0,
      'warned': 0.0,
      'switched': 0.0,
      'max_budget': max(cost_settings.max_budget_usd, 0.0),
      'warn_percent': max(min(cost_settings.warn_percent or 0.8, 1.0), 0.05),
      'auto_switch': 1.0 if cost_settings.auto_switch_model else 0.0
    }

  def seed(self, session_id: str, total_cost: float) -> None:
    state = self._sessions.get(session_id)
    if not state:
      return
    state['total_cost'] = max(total_cost, 0.0)

  def estimate_usd(self, model_identifier: str, tokens: int) -> float:
    rate = MODEL_PRICING_PER_1K.get(model_identifier, 0.02)
    return round(rate * (tokens / 1000.0), 4)

  def update(self, session_id: str, settings: CostSettings, additional_cost: float) -> CostUpdate:
    if session_id not in self._sessions:
      self.start(session_id, settings)
    state = self._sessions[session_id]
    state['total_cost'] += additional_cost
    total_cost = state['total_cost']
    max_budget = state['max_budget']

    percent_consumed = 0.0
    if settings.enabled and max_budget > 0:
      percent_consumed = min(total_cost / max_budget, 10.0)

    warning = None
    switched = False

    warn_threshold = state['warn_percent']
    if settings.enabled and max_budget > 0:
      if percent_consumed >= 1.0:
        warning = f'Cost limit reached (${total_cost:.2f} / ${max_budget:.2f}). Session halted.'
        if self._event_logger:
          self._event_logger.log_event('cost_limit_reached', warning, {'session_id': session_id})
        return CostUpdate(
          continue_processing=False,
          total_cost=total_cost,
          percent_consumed=percent_consumed,
          warning=warning
        )
      if percent_consumed >= warn_threshold and state['warned'] == 0.0:
        warning = f'Cost budget at {percent_consumed * 100:.0f}% (${total_cost:.2f} / ${max_budget:.2f}).'
        state['warned'] = percent_consumed
        if self._event_logger:
          self._event_logger.log_event('cost_budget_warning', warning, {'session_id': session_id})
        if settings.auto_switch_model and not state['switched']:
          switched = True
          state['switched'] = percent_consumed
    return CostUpdate(
      continue_processing=True,
      total_cost=total_cost,
      percent_consumed=percent_consumed,
      warning=warning,
      switched_model=switched
    )

  def summary(self, session_id: str) -> Optional[Dict[str, float]]:
    state = self._sessions.get(session_id)
    if not state:
      return None
    return {
      'total_cost': state['total_cost'],
      'warned': state['warned'],
      'switched': state['switched'],
      'max_budget': state['max_budget']
    }

  def finish(self, session_id: str) -> None:
    self._sessions.pop(session_id, None)
