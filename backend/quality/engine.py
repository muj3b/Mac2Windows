from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import List, Iterable, TYPE_CHECKING

from backend.conversion.models import QualityIssue, QualityReport, ChunkWorkItem
from backend.conversion.mappings import DependencyMapping, ApiMappingCatalog
from backend.ai.orchestrator import AIOrchestrator, OrchestrationConfig
from backend.security.scanner import scan_dependency_file

if TYPE_CHECKING:
  from backend.conversion.manager import ConversionSession

logger = logging.getLogger(__name__)


class QualityEngine:
  """Runs post-conversion verification, AI self-review, and reporting."""

  def __init__(
    self,
    dependency_mapping: DependencyMapping,
    api_mapping: ApiMappingCatalog,
    orchestrator: AIOrchestrator
  ) -> None:
    self.dependency_mapping = dependency_mapping
    self.api_mapping = api_mapping
    self.orchestrator = orchestrator

  async def evaluate(self, session: 'ConversionSession') -> QualityReport:
    report = QualityReport()
    report.issues.extend(self._syntax_checks(session, report))
    report.issues.extend(self._resource_checks(session, report))
    report.issues.extend(self._dependency_checks(session, report))
    report.issues.extend(self._api_checks(session, report))
    report.issues.extend(self._security_checks(session, report))

    try:
      ai_notes = await self._ai_self_review(session)
      report.ai_review_notes.extend(ai_notes)
    except Exception as error:  # pragma: no cover - defensive
      logger.exception('AI self-review failed: %s', error)
      report.ai_review_notes.append(f'AI self-review unavailable: {error}')
    return report

  def _syntax_checks(self, session: 'ConversionSession', report: QualityReport) -> List[QualityIssue]:
    issues: List[QualityIssue] = []
    for file_path in session.target_path.rglob('*'):
      if not file_path.is_file():
        continue
      suffix = file_path.suffix.lower()
      if suffix not in {'.cs', '.swift', '.m', '.mm', '.xaml'}:
        continue
      try:
        text = file_path.read_text(encoding='utf-8', errors='ignore')
      except OSError:
        continue
      if text.count('{') != text.count('}'):
        report.syntax_passed = False
        issues.append(
          QualityIssue(
            category='syntax',
            message='Mismatched braces detected',
            severity='error',
            file_path=str(file_path)
          )
        )
      if suffix == '.xaml' and '<Page' not in text and '<Window' not in text:
        report.syntax_passed = False
        issues.append(
          QualityIssue(
            category='syntax',
            message='XAML file missing root element',
            severity='warning',
            file_path=str(file_path)
          )
        )
    return issues

  def _resource_checks(self, session: 'ConversionSession', report: QualityReport) -> List[QualityIssue]:
    issues: List[QualityIssue] = []
    required_resources = []
    for chunk in session.chunks.values():
      if chunk.chunk.stage.name == 'RESOURCES' and chunk.output_path:
        required_resources.append(chunk.output_path)
    for resource in required_resources:
      if not resource.exists():
        report.resources_ok = False
        issues.append(
          QualityIssue(
            category='resource',
            message='Expected resource not generated',
            severity='error',
            file_path=str(resource)
          )
        )
    return issues

  def _dependency_checks(self, session: 'ConversionSession', report: QualityReport) -> List[QualityIssue]:
    issues: List[QualityIssue] = []
    mapping = self.dependency_mapping.directional_map(session.direction)
    reverse_mapping = {v: k for k, v in mapping.items()}
    for chunk in session.chunks.values():
      if not chunk.summary:
        continue
      for source_dep, target_dep in mapping.items():
        if source_dep in chunk.summary and target_dep not in chunk.summary:
          report.dependency_ok = False
          issues.append(
            QualityIssue(
              category='dependency',
              message=f'Dependency {source_dep} not mapped to {target_dep}',
              severity='warning',
              file_path=str(chunk.chunk.file_path)
            )
          )
    for target_dep, source_dep in reverse_mapping.items():
        if target_dep in chunk.summary and source_dep not in chunk.summary:
          report.dependency_ok = False
          issues.append(
            QualityIssue(
              category='dependency',
              message=f'Target dependency {target_dep} lacks reference to source {source_dep}',
              severity='warning',
              file_path=str(chunk.chunk.file_path)
            )
          )
    for config_file in session.target_path.rglob('packages.config'):
      issues.extend(scan_dependency_file(config_file))
    for manifest in session.target_path.rglob('*.json'):
      if manifest.name.lower() in {'package.json', 'deps.json'}:
        issues.extend(scan_dependency_file(manifest))
    return issues

  def _api_checks(self, session: 'ConversionSession', report: QualityReport) -> List[QualityIssue]:
    mapping = self.api_mapping.directional_map(session.direction)
    issues: List[QualityIssue] = []
    for chunk in session.chunks.values():
      if not chunk.summary:
        continue
      for source_api, target_api in mapping.items():
        if source_api in chunk.summary and target_api not in chunk.summary:
          report.api_ok = False
          issues.append(
            QualityIssue(
              category='api-mapping',
              message=f'API {source_api} not translated to {target_api}',
              severity='warning',
              file_path=str(chunk.chunk.file_path)
            )
          )
    return issues

  def _security_checks(self, session: 'ConversionSession', report: QualityReport) -> List[QualityIssue]:
    forbidden_tokens = {'password', 'secret', 'api_key', 'token', 'privatekey'}
    issues: List[QualityIssue] = []
    for file_path in session.target_path.rglob('*'):
      if not file_path.is_file():
        continue
      try:
        text = file_path.read_text(encoding='utf-8', errors='ignore')
      except OSError:
        continue
      lowered = text.lower()
      for token in forbidden_tokens:
        if token in lowered:
          report.security_ok = False
          issues.append(
            QualityIssue(
              category='security',
              message=f'Potential secret detected ({token})',
              severity='error',
              file_path=str(file_path)
            )
          )
    return issues

  async def _ai_self_review(self, session: 'ConversionSession') -> List[str]:
    review_notes: List[str] = []
    sample_files = list(self._sample_converted_files(session.target_path, limit=5))
    for file_path in sample_files:
      try:
        content = file_path.read_text(encoding='utf-8', errors='ignore')
      except OSError:
        continue
      chunk = ChunkWorkItem(
        file_path=file_path,
        language=file_path.suffix.lower().lstrip('.'),
        start_line=1,
        end_line=len(content.splitlines()),
        content=content,
        chunk_id=f'review::{file_path.name}'
      )
      response = await self.orchestrator.convert_chunk(
        chunk=chunk,
        config=OrchestrationConfig(
          provider_id=session.orchestrator_config.provider_id,
          model_identifier=session.orchestrator_config.model_identifier,
          api_key=session.orchestrator_config.api_key
        ),
        ai_settings=session.ai_settings,
        direction=session.direction,
        rag_context=[],
        previous_summary='Self-review focus on logic correctness.'
      )
      note = response.get('summary', '')
      if not note:
        continue
      if 'issue' in note.lower():
        review_notes.append(f'{file_path.name}: {note}')
      else:
        review_notes.append(f'{file_path.name}: Review passed.')
    return review_notes

  def _sample_converted_files(self, target_path: Path, limit: int = 5) -> Iterable[Path]:
    count = 0
    for file_path in target_path.rglob('*'):
      if not file_path.is_file():
        continue
      if file_path.suffix.lower() not in {'.cs', '.swift', '.xaml'}:
        continue
      yield file_path
      count += 1
      if count >= limit:
        break
