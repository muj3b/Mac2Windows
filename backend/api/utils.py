from typing import Optional, Dict, Any

def serialize_summary(summary: Optional[Any]) -> Optional[Dict[str, Any]]:
  if not summary:
    return None
  return {
    'overall_percentage': summary.overall_percentage,
    'tokens_used': summary.tokens_used,
    'cost_usd': summary.cost_usd,
    'elapsed_seconds': summary.elapsed_seconds,
    'estimated_seconds_remaining': summary.estimated_seconds_remaining,
    'converted_files': summary.converted_files,
    'total_files': summary.total_files,
    'paused': summary.paused,
    'direction': summary.direction,
    'current_chunk': serialize_chunk(summary.current_chunk),
    'stage_progress': {
      stage.name: {
        'completed_units': progress.completed_units,
        'total_units': progress.total_units,
        'status': progress.status,
        'percentage': progress.percentage
      }
      for stage, progress in summary.stage_progress.items()
    },
    'quality_report': summary.quality_report.summary() if summary.quality_report else None,
    'conversion_report': str(summary.conversion_report.summary_html) if summary.conversion_report else None,
    'manual_fixes_pending': summary.manual_fixes_pending,
    'backups': summary.backups,
    'test_results': summary.test_results,
    'benchmarks': summary.benchmarks,
    'cleanup_report': summary.cleanup_report.summary() if summary.cleanup_report else None,
    'quality_score': summary.quality_score,
    'warnings': summary.warnings,
    'cost_settings': summary.cost_settings.__dict__ if summary.cost_settings else None,
    'cost_percent_consumed': summary.cost_percent_consumed,
    'project_type': summary.project_type,
    'offline_mode': summary.offline_mode,
    'preview_estimate': summary.preview_estimate.summary() if summary.preview_estimate else None
  }

def serialize_chunk(chunk: Optional[Any]) -> Optional[Dict[str, Any]]:
  if not chunk:
    return None
  return {
    'chunk_id': chunk.chunk.chunk_id,
    'file_path': str(chunk.chunk.file_path),
    'stage': chunk.chunk.stage.name,
    'status': chunk.status.name,
    'tokens_used': chunk.tokens_used,
    'cost_usd': chunk.cost_usd,
    'summary': chunk.summary,
    'output_path': str(chunk.output_path) if chunk.output_path else None,
    'model_identifier': chunk.ai_model,
    'provider_id': chunk.provider_id
  }
