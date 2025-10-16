from __future__ import annotations

import difflib
import json
from pathlib import Path
from typing import List, TYPE_CHECKING

from backend.conversion.models import ConversionReport, DiffArtifact
from backend.conversion.diff import generate_side_by_side

if TYPE_CHECKING:
  from backend.conversion.manager import ConversionSession


def generate_conversion_report(session: 'ConversionSession') -> ConversionReport:
  reports_dir = session.target_path / 'reports'
  reports_dir.mkdir(parents=True, exist_ok=True)

  diff_artifacts: List[DiffArtifact] = []
  for record in session.chunks.values():
    if not record.output_path or not record.chunk.file_path.exists():
      continue
    try:
      original_lines = record.chunk.file_path.read_text(encoding='utf-8', errors='ignore').splitlines()
      converted_lines = record.output_path.read_text(encoding='utf-8', errors='ignore').splitlines()
    except OSError:
      continue
    diff_path = reports_dir / f"diff_{record.chunk.chunk_id.replace(':', '_')}.html"
    generate_side_by_side(record.chunk.file_path, record.output_path, diff_path)
    diff_artifacts.append(
      DiffArtifact(
        source_path=record.chunk.file_path,
        target_path=record.output_path,
        diff_html_path=diff_path
      )
    )

  summary_path = reports_dir / 'conversion_report.html'
  quality_summary = session.quality_report.summary() if session.quality_report else {}
  summary = {
    'session_id': session.session_id,
    'direction': session.direction,
    'converted_files': sum(1 for record in session.chunks.values() if record.status.name == 'COMPLETED'),
    'total_files': len(session.chunks),
    'quality': quality_summary,
    'notes': session.summary_notes,
    'webhooks': session.webhooks
  }
  summary_html = '<html><head><title>Conversion Report</title></head><body>'
  summary_html += f'<h1>Conversion Summary for {session.session_id}</h1>'
  summary_html += f'<p>Direction: {session.direction}</p>'
  summary_html += f'<p>Converted files: {summary["converted_files"]} / {summary["total_files"]}</p>'
  if session.quality_report:
    summary_html += '<h2>Quality Report</h2>'
    summary_html += '<ul>'
    for issue in session.quality_report.issues:
      summary_html += f'<li>[{issue.severity}] {issue.category}: {issue.message} ({issue.file_path or "n/a"})</li>'
    summary_html += '</ul>'
  summary_html += '<h2>Diff Artifacts</h2><ul>'
  for artifact in diff_artifacts:
    rel = artifact.diff_html_path.name
    summary_html += f'<li><a href="{rel}">{artifact.target_path.name}</a></li>'
  summary_html += '</ul>'
  summary_html += '</body></html>'
  summary_path.write_text(summary_html, encoding='utf-8')

  return ConversionReport(
    summary_html=summary_path,
    diff_artifacts=diff_artifacts,
    generated_at=session.updated_at,
    metadata=summary
  )
