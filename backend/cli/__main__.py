from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Optional

from backend.config import settings

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
logger = logging.getLogger(__name__)


def build_manager():
  from backend.ai.provider_registry import ProviderRegistry
  from backend.conversion.manager import ConversionManager
  from backend.conversion.mappings import DEPENDENCY_MAP, API_MAP, DependencyMapping, ApiMappingCatalog
  from backend.resources.monitor import ResourceMonitor
  from backend.storage.embeddings import EmbeddingStore
  from backend.conversion.session_store import ConversionSessionStore
  from backend.logging.event_logger import EventLogger
  from backend.learning.memory import LearningMemory

  providers = ProviderRegistry()
  resources = ResourceMonitor()
  embedding_store = EmbeddingStore(settings.chroma_path)
  session_store = ConversionSessionStore(settings.db_path)
  event_logger = EventLogger(settings.data_dir / 'logs')
  learning_memory = LearningMemory(settings.data_dir / 'learning_memory.json')
  backup_manager = None
  try:
    from backend.security.secret_manager import SecretManager
    from backend.storage.credentials import CredentialStore
    from backend.storage.backup import BackupManager
    secret_manager = SecretManager(settings.secret_key_path)
    credential_store = CredentialStore(settings.credentials_db_path, secret_manager)
    backup_manager = BackupManager(credential_store, settings.backup_root)
  except Exception:
    backup_manager = None
  return ConversionManager(
    provider_registry=providers,
    dependency_mapping=DependencyMapping(DEPENDENCY_MAP),
    api_mapping=ApiMappingCatalog(API_MAP),
    embedding_store=embedding_store,
    session_store=session_store,
    resource_monitor=resources,
    backup_manager=backup_manager,
    event_logger=event_logger,
    learning_memory=learning_memory
  )


def parse_global_args() -> argparse.ArgumentParser:
  parser = argparse.ArgumentParser(prog='macwin', description='Mac ↔ Windows converter CLI')
  sub = parser.add_subparsers(dest='command', required=True)

  p_analyze = sub.add_parser('analyze', help='Analyze a project and suggest targets')
  p_analyze.add_argument('--src', required=True)
  p_analyze.add_argument('--direction', choices=['mac-to-win', 'win-to-mac'])
  p_analyze.add_argument('--json', action='store_true')

  p_preview = sub.add_parser('preview', help='Estimate conversion effort and cost')
  p_preview.add_argument('--src', required=True)
  p_preview.add_argument('--direction', required=True, choices=['mac-to-win', 'win-to-mac'])
  p_preview.add_argument('--exclusions', nargs='*')
  p_preview.add_argument('--model', default='gpt-5')

  p_convert = sub.add_parser('convert', help='Run a conversion and wait for completion')
  p_convert.add_argument('--src', required=True)
  p_convert.add_argument('--out', required=True)
  p_convert.add_argument('--direction', required=True, choices=['mac-to-win', 'win-to-mac'])
  p_convert.add_argument('--provider', default='ollama')
  p_convert.add_argument('--model', default='gpt-5-nano')
  p_convert.add_argument('--api-key')
  p_convert.add_argument('--preview', action='store_true')
  p_convert.add_argument('--exclusions', nargs='*')
  p_convert.add_argument('--prefer-offline', action='store_true')
  p_convert.add_argument('--max-cpu', type=int, default=80)
  p_convert.add_argument('--max-ram-gb', type=int, default=16)
  p_convert.add_argument('--threads', type=int, default=4)
  p_convert.add_argument('--build-timeout-seconds', type=int, default=600)
  p_convert.add_argument('--budget-usd', type=float, default=50.0)
  p_convert.add_argument('--json', action='store_true')

  p_compile = sub.add_parser('compile', help='Compile a generated target project')
  p_compile.add_argument('--target', required=True)
  p_compile.add_argument('--direction', required=True, choices=['mac-to-win', 'win-to-mac'])

  p_report = sub.add_parser('report', help='Show summary for a session')
  p_report.add_argument('--session-id', required=True)
  p_report.add_argument('--json', action='store_true')

  return parser


def cmd_analyze(src: str, direction: Optional[str], as_json: bool) -> int:
  from backend.detection.scanner import ProjectScanner, ScannerError
  scanner = ProjectScanner(settings=settings)
  try:
    result = asyncio.run(scanner.scan(src, direction=direction))
  except ScannerError as exc:
    print(str(exc), file=sys.stderr)
    return 2
  if as_json:
    print(json.dumps(result, indent=2))
  else:
    hints = result.get('language_hints') or {}
    frameworks = result.get('frameworks') or []
    print(f"Project: {src}")
    print(f"Direction: {direction or 'auto'}")
    print(f"Languages: {', '.join(hints.keys()) or 'unknown'}")
    print(f"Frameworks: {', '.join(frameworks) or 'unknown'}")
    print(f"Suggested targets: {', '.join(result.get('suggested_targets') or [])}")
  return 0


def _build_settings(namespace: argparse.Namespace) -> tuple[ConversionSettings, PerformanceSettings, AISettings, GitSettings, BackupSettings, CostSettings]:
  conversion = ConversionSettings(
    preview_mode=bool(namespace.preview),
    exclusions=namespace.exclusions or []
  )
  performance = PerformanceSettings(
    prefer_offline=bool(namespace.prefer_offline),
    max_cpu=namespace.max_cpu,
    max_ram_gb=namespace.max_ram_gb,
    threads=namespace.threads,
    build_timeout_seconds=namespace.build_timeout_seconds
  )
  ai = AISettings()
  git = GitSettings(
    enabled=settings.git_enabled,
    tag_prefix=settings.git_tag_prefix,
    branch=settings.git_branch
  )
  backup = BackupSettings(
    enabled=False,
    provider=settings.default_backup_provider
  )
  cost = CostSettings(
    enabled=True,
    max_budget_usd=namespace.budget_usd
  )
  return conversion, performance, ai, git, backup, cost


def cmd_preview(manager, src: str, direction: str, exclusions: list[str], model: str) -> int:
  project_path = Path(src).expanduser().resolve()
  if not project_path.exists() or not project_path.is_dir():
    print('Project path does not exist or is not a directory.', file=sys.stderr)
    return 2
  estimate = manager.generate_preview(project_path, direction, exclusions or [])
  cost = manager.cost_tracker.estimate_usd(model, estimate.estimated_tokens)
  summary = estimate.summary()
  summary['estimated_cost_usd'] = cost
  summary['model_identifier'] = model
  print(json.dumps({'preview': summary}, indent=2))
  return 0


def _print_progress(manager, session_id: str, as_json: bool) -> None:
  last_print = 0.0
  while True:
    summary = manager.get_summary(session_id)
    if not summary:
      break
    percent = summary.overall_percentage
    if as_json:
      payload = {
        'session_id': session_id,
        'overall_percentage': percent,
        'tokens_used': summary.tokens_used,
        'cost_usd': summary.cost_usd,
        'elapsed_seconds': summary.elapsed_seconds,
        'estimated_seconds_remaining': summary.estimated_seconds_remaining,
        'converted_files': summary.converted_files,
        'total_files': summary.total_files,
        'paused': summary.paused,
        'direction': summary.direction
      }
      print(json.dumps(payload))
    else:
      now = time.time()
      if now - last_print >= 0.5:
        bar = int(percent) // 2
        print(f"[{('#' * bar).ljust(50)}] {percent:.1f}%  files {summary.converted_files}/{summary.total_files}  cost ${summary.cost_usd:.2f}", end='\r', flush=True)
        last_print = now
    if percent >= 100.0 or (summary.test_results and summary.quality_report):
      print()
      break
    time.sleep(0.5)


def cmd_convert(manager, ns: argparse.Namespace) -> int:
  src = Path(ns.src).expanduser().resolve()
  out = Path(ns.out).expanduser().resolve()
  if not src.exists() or not src.is_dir():
    print('Project path does not exist or is not a directory.', file=sys.stderr)
    return 2
  out.mkdir(parents=True, exist_ok=True)
  conversion, performance, ai, git, backup, cost = _build_settings(ns)
  preview_estimate = None
  if conversion.preview_mode:
    try:
      preview_estimate = manager.generate_preview(src, ns.direction, conversion.exclusions or [])
    except Exception:
      preview_estimate = None
  session = manager.start_session(
    project_path=src,
    target_path=out,
    direction=ns.direction,
    provider_id=ns.provider,
    model_identifier=ns.model,
    api_key=ns.api_key,
    conversion_settings=conversion,
    performance_settings=performance,
    ai_settings=ai,
    webhooks=[],
    incremental=False,
    git_settings=git,
    backup_settings=backup,
    cost_settings=cost,
    preview_estimate=preview_estimate
  )
  _print_progress(manager, session.session_id, ns.json)
  summary = manager.get_summary(session.session_id)
  payload: dict[str, Any] = {
    'session_id': session.session_id,
    'overall_percentage': summary.overall_percentage if summary else 0.0,
    'output_dir': str(out),
    'direction': ns.direction,
    'cost_usd': summary.cost_usd if summary else 0.0,
    'quality_score': summary.quality_score if summary else None
  }
  print(json.dumps(payload, indent=2))
  return 0


def cmd_compile(target: str, direction: str) -> int:
  from backend.conversion.validators import ValidationEngine
  engine = ValidationEngine()
  root = Path(target).expanduser().resolve()
  if direction == 'mac-to-win':
    issues = engine.validate_windows_project(root)
  else:
    issues = engine.validate_mac_project(root)
  errors = [i for i in issues if getattr(i, 'severity', '').lower() == 'error']
  print(json.dumps({'issues': [i.__dict__ for i in issues]}, indent=2))
  return 1 if errors else 0


def cmd_report(manager, session_id: str, as_json: bool) -> int:
  summary = manager.get_summary(session_id)
  if not summary:
    print('Session not found.', file=sys.stderr)
    return 2
  if as_json:
    payload = {
      'overall_percentage': summary.overall_percentage,
      'tokens_used': summary.tokens_used,
      'cost_usd': summary.cost_usd,
      'quality_score': summary.quality_score,
      'cleanup_report': summary.cleanup_report.summary() if summary.cleanup_report else None,
      'quality_report': summary.quality_report.summary() if summary.quality_report else None,
      'conversion_report': str(summary.conversion_report.summary_html) if summary.conversion_report else None
    }
    print(json.dumps(payload, indent=2))
  else:
    print(f"Progress: {summary.overall_percentage:.1f}%  Cost: ${summary.cost_usd:.2f}  Quality: {summary.quality_score}")
  return 0


def main() -> int:
  parser = parse_global_args()
  ns = parser.parse_args()
  cmd = ns.command
  if cmd == 'analyze':
    return cmd_analyze(ns.src, ns.direction, ns.json)
  manager = build_manager()
  if cmd == 'preview':
    return cmd_preview(manager, ns.src, ns.direction, ns.exclusions or [], ns.model)
  if cmd == 'convert':
    return cmd_convert(manager, ns)
  if cmd == 'compile':
    return cmd_compile(ns.target, ns.direction)
  if cmd == 'report':
    return cmd_report(manager, ns.session_id, ns.json)
  return 1


if __name__ == '__main__':
  raise SystemExit(main())
