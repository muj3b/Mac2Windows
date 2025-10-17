from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional


class Stage(Enum):
  RESOURCES = auto()
  DEPENDENCIES = auto()
  PROJECT_SETUP = auto()
  CODE = auto()
  TESTS = auto()
  QUALITY = auto()


STAGE_ORDER = [
  Stage.RESOURCES,
  Stage.DEPENDENCIES,
  Stage.PROJECT_SETUP,
  Stage.CODE,
  Stage.TESTS,
  Stage.QUALITY
]


STAGE_WEIGHTS = {
  Stage.RESOURCES: 0.10,
  Stage.DEPENDENCIES: 0.10,
  Stage.PROJECT_SETUP: 0.05,
  Stage.CODE: 0.60,
  Stage.TESTS: 0.10,
  Stage.QUALITY: 0.05
}


@dataclass
class WebhookConfig:
  url: str
  headers: Dict[str, str] = field(default_factory=dict)
  events: List[str] = field(default_factory=lambda: ['conversion.started', 'conversion.completed', 'conversion.failed'])
  secret_token: Optional[str] = None

  def should_fire(self, event_name: str) -> bool:
    if not self.events:
      return True
    normalized = event_name.lower()
    return any(event.lower() == normalized for event in self.events)

  def as_dict(self) -> Dict[str, Any]:
    return {
      'url': self.url,
      'headers': self.headers,
      'events': self.events,
      'secret_token': self.secret_token
    }


@dataclass
class CostSettings:
  enabled: bool = True
  max_budget_usd: float = 50.0
  warn_percent: float = 0.8
  auto_switch_model: bool = True
  fallback_model_identifier: Optional[str] = None
  fallback_provider_id: Optional[str] = None


@dataclass
class CleanupReport:
  unused_assets: List[str] = field(default_factory=list)
  unused_dependencies: List[str] = field(default_factory=list)
  total_bytes_reclaimed: int = 0
  auto_deleted: List[str] = field(default_factory=list)
  scanned_assets: int = 0
  scanned_dependencies: int = 0

  def summary(self) -> Dict[str, Any]:
    return {
      'unused_assets': self.unused_assets,
      'unused_dependencies': self.unused_dependencies,
      'total_bytes_reclaimed': self.total_bytes_reclaimed,
      'auto_deleted': self.auto_deleted,
      'scanned_assets': self.scanned_assets,
      'scanned_dependencies': self.scanned_dependencies
    }


@dataclass
class PreviewEstimate:
  total_files: int = 0
  impacted_files: int = 0
  estimated_tokens: int = 0
  estimated_cost_usd: float = 0.0
  estimated_minutes: float = 0.0
  stage_breakdown: Dict[str, Dict[str, Any]] = field(default_factory=dict)

  def summary(self) -> Dict[str, Any]:
    return {
      'total_files': self.total_files,
      'impacted_files': self.impacted_files,
      'estimated_tokens': self.estimated_tokens,
      'estimated_cost_usd': self.estimated_cost_usd,
      'estimated_minutes': self.estimated_minutes,
      'stage_breakdown': self.stage_breakdown
    }


@dataclass
class StageProgress:
  stage: Stage
  completed_units: int = 0
  total_units: int = 0
  status: str = 'pending'  # pending, running, paused, completed, skipped

  @property
  def percentage(self) -> float:
    if self.total_units == 0:
      return 0.0
    return min(1.0, self.completed_units / self.total_units)


@dataclass
class ChunkWorkItem:
  file_path: Path
  language: str
  start_line: int
  end_line: int
  content: str
  dependencies: List[str] = field(default_factory=list)
  symbols: List[str] = field(default_factory=list)
  summary: Optional[str] = None
  stage: Stage = Stage.CODE
  chunk_id: str = ''
  checksum: Optional[str] = None


class ChunkStatus(Enum):
  PENDING = auto()
  IN_PROGRESS = auto()
  COMPLETED = auto()
  FAILED = auto()
  SKIPPED = auto()


@dataclass
class ChunkRecord:
  chunk: ChunkWorkItem
  status: ChunkStatus = ChunkStatus.PENDING
  output_path: Optional[Path] = None
  last_error: Optional[str] = None
  tokens_used: int = 0
  cost_usd: float = 0.0
  ai_model: Optional[str] = None
  provider_id: Optional[str] = None
  summary: Optional[str] = None
  partial_completion: bool = False
  raw_output: Optional[str] = None
  input_tokens: int = 0
  output_tokens: int = 0


@dataclass
class QualityIssue:
  category: str
  message: str
  severity: str = 'warning'
  file_path: Optional[str] = None
  line: Optional[int] = None


@dataclass
class ManualFixEntry:
  chunk_id: str
  file_path: str
  reason: str
  notes: List[str] = field(default_factory=list)
  status: str = 'pending'  # pending, applied, skipped
  override_path: Optional[str] = None
  submitted_by: Optional[str] = None
  timestamp: Optional[float] = None
  fingerprint: Optional[str] = None

  def to_dict(self) -> Dict[str, Any]:
    return {
      'chunk_id': self.chunk_id,
      'file_path': self.file_path,
      'reason': self.reason,
      'notes': self.notes,
      'status': self.status,
      'override_path': self.override_path,
      'submitted_by': self.submitted_by,
      'timestamp': self.timestamp,
      'fingerprint': self.fingerprint
    }


@dataclass
class QualityReport:
  issues: List[QualityIssue] = field(default_factory=list)
  syntax_passed: bool = True
  build_passed: bool = True
  dependency_ok: bool = True
  resources_ok: bool = True
  api_ok: bool = True
  security_ok: bool = True
  ai_review_notes: List[str] = field(default_factory=list)
  flagged_chunks: List[str] = field(default_factory=list)

  def summary(self) -> Dict[str, Any]:
    return {
      'issues': [issue.__dict__ for issue in self.issues],
      'syntax_passed': self.syntax_passed,
      'build_passed': self.build_passed,
      'dependency_ok': self.dependency_ok,
      'resources_ok': self.resources_ok,
      'api_ok': self.api_ok,
      'security_ok': self.security_ok,
      'ai_review_notes': self.ai_review_notes,
      'flagged_chunks': self.flagged_chunks
    }


@dataclass
class DiffArtifact:
  source_path: Path
  target_path: Path
  diff_html_path: Path


@dataclass
class ConversionReport:
  summary_html: Path
  diff_artifacts: List[DiffArtifact] = field(default_factory=list)
  generated_at: float = 0.0
  metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConversionSettings:
  code_style: str = 'native'
  comments: str = 'keep'
  naming: str = 'preserve'
  error_handling: str = 'adapt'
  self_review: bool = True
  optimize_assets: bool = True
  image_quality: int = 85
  max_image_megapixels: float = 4.0
  cleanup_unused_assets: bool = True
  cleanup_auto_delete: bool = False
  cleanup_min_bytes: int = 1024 * 1024
  preview_mode: bool = False
  manual_fix_autofill: bool = True
  quality_score_threshold: float = 0.7
  project_type: Optional[str] = None
  exclusions: List[str] = field(default_factory=list)
  enable_learning: bool = True
  learning_trigger_count: int = 3


@dataclass
class PerformanceSettings:
  max_cpu: int = 80
  max_ram_gb: int = 16
  threads: int = 4
  api_rate_limit: int = 30
  parallel_conversions: int = 1
  build_timeout_seconds: int = 600
  prefer_offline: bool = False


@dataclass
class AISettings:
  temperature: float = 0.2
  strategy: str = 'balanced'
  retries: int = 3
  offline_only: bool = False
  prompt_tone: str = 'pro'
  fallback_model_identifier: Optional[str] = None
  fallback_provider_id: Optional[str] = None
  smart_prompting: bool = True


@dataclass
class GitSettings:
  enabled: bool = True
  tag_after_completion: bool = False
  tag_prefix: str = 'conversion'
  branch: Optional[str] = None


@dataclass
class BackupSettings:
  enabled: bool = False
  provider: str = 'local'
  retention_count: int = 10
  remote_path: str = '{project}/{direction}'
  credential_id: Optional[str] = None


@dataclass
class ConversionSummary:
  total_files: int
  converted_files: int
  elapsed_seconds: float
  estimated_seconds_remaining: Optional[float]
  tokens_used: int
  cost_usd: float
  stage_progress: Dict[Stage, StageProgress]
  current_chunk: Optional[ChunkRecord] = None
  overall_percentage: float = 0.0
  paused: bool = False
  direction: str = 'mac-to-win'
  errors: List[str] = field(default_factory=list)
  quality_report: Optional[QualityReport] = None
  conversion_report: Optional[ConversionReport] = None
  manual_fixes_pending: int = 0
  backups: List[Dict[str, Any]] = field(default_factory=list)
  test_results: Optional[Dict[str, Any]] = None
  benchmarks: Dict[str, Any] = field(default_factory=dict)
  cleanup_report: Optional[CleanupReport] = None
  quality_score: Optional[float] = None
  warnings: List[str] = field(default_factory=list)
  cost_settings: Optional[CostSettings] = None
  cost_percent_consumed: Optional[float] = None
  project_type: Optional[str] = None
  offline_mode: bool = False
  preview_estimate: Optional[PreviewEstimate] = None


@dataclass
class SymbolTableEntry:
  identifier: str
  kind: str
  location: str
  metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class SessionState:
  session_id: str
  project_path: Path
  target_path: Path
  direction: str
  stage_progress: Dict[Stage, StageProgress]
  chunks: Dict[str, ChunkRecord]
  created_at: float
  updated_at: float
  paused: bool = False
  summary_notes: List[str] = field(default_factory=list)
  symbol_table: Dict[str, SymbolTableEntry] = field(default_factory=dict)
  quality_report: Optional[QualityReport] = None
  conversion_settings: ConversionSettings = field(default_factory=ConversionSettings)
  performance_settings: PerformanceSettings = field(default_factory=PerformanceSettings)
  ai_settings: AISettings = field(default_factory=AISettings)
  backup_settings: BackupSettings = field(default_factory=BackupSettings)
  webhooks: List[Dict[str, Any]] = field(default_factory=list)
  conversion_report: Optional[ConversionReport] = None
  incremental: bool = False
  git_settings: GitSettings = field(default_factory=GitSettings)
  manual_queue: Dict[str, ManualFixEntry] = field(default_factory=dict)
  test_results: Optional[Dict[str, Any]] = None
  benchmarks: Dict[str, Any] = field(default_factory=dict)
  cost_settings: CostSettings = field(default_factory=CostSettings)
  cleanup_report: Optional[CleanupReport] = None
  preview_estimate: Optional[PreviewEstimate] = None
