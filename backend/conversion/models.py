from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Dict, List, Optional, Any


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


@dataclass
class PerformanceSettings:
  max_cpu: int = 80
  max_ram_gb: int = 16
  threads: int = 4
  api_rate_limit: int = 30


@dataclass
class AISettings:
  temperature: float = 0.2
  strategy: str = 'balanced'
  retries: int = 3


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
  webhooks: List[str] = field(default_factory=list)
  conversion_report: Optional[ConversionReport] = None
  incremental: bool = False
