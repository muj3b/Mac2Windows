from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class Settings:
  """Global backend configuration derived from environment variables."""

  backend_host: str = os.getenv('BACKEND_HOST', '127.0.0.1')
  backend_port: int = int(os.getenv('BACKEND_PORT', '6110'))
  log_level: str = os.getenv('BACKEND_LOG_LEVEL', 'info')
  data_dir: Path = Path(os.getenv('CONVERTER_DATA_DIR', './data')).resolve()
  db_path: Path = Path(os.getenv('CONVERTER_DB_PATH', './data/state.db')).resolve()
  chroma_path: Path = Path(os.getenv('CONVERTER_CHROMA_PATH', './data/chroma')).resolve()
  max_line_count_bytes: int = int(os.getenv('CONVERTER_MAX_LINE_COUNT_BYTES', str(6 * 1024 * 1024)))
  max_preview_bytes: int = int(os.getenv('CONVERTER_MAX_PREVIEW_BYTES', str(64 * 1024)))
  anthropic_api_key: Optional[str] = os.getenv('ANTHROPIC_API_KEY')
  anthropic_api_url: str = os.getenv('ANTHROPIC_API_URL', 'https://api.anthropic.com')
  openai_api_key: Optional[str] = os.getenv('OPENAI_API_KEY')
  openai_base_url: str = os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1')
  openai_organization: Optional[str] = os.getenv('OPENAI_ORG_ID')
  ollama_base_url: str = os.getenv('OLLAMA_BASE_URL', 'http://127.0.0.1:11434')
  request_timeout_seconds: float = float(os.getenv('CONVERTER_REQUEST_TIMEOUT', '60'))
  ai_retry_attempts: int = int(os.getenv('CONVERTER_AI_RETRY_ATTEMPTS', '3'))
  ai_retry_backoff_seconds: float = float(os.getenv('CONVERTER_AI_RETRY_BACKOFF', '2'))
  incremental_cache_path: Path = Path(os.getenv('CONVERTER_INCREMENTAL_CACHE', './data/incremental.json')).resolve()
  git_enabled: bool = os.getenv('CONVERTER_GIT_ENABLED', 'true').lower() == 'true'
  git_tag_prefix: str = os.getenv('CONVERTER_GIT_TAG_PREFIX', 'conversion')
  git_branch: Optional[str] = os.getenv('CONVERTER_GIT_BRANCH')
  credentials_db_path: Path = Path(os.getenv('CONVERTER_CREDENTIAL_DB', './data/credentials.db')).resolve()
  secrets_dir: Path = Path(os.getenv('CONVERTER_SECRETS_DIR', './data/secrets')).resolve()
  secret_key_path: Path = Path(os.getenv('CONVERTER_SECRET_KEY_PATH', './data/secrets/fernet.key')).resolve()
  backup_root: Path = Path(os.getenv('CONVERTER_BACKUP_ROOT', './data/cloud_backups')).resolve()
  default_backup_provider: str = os.getenv('CONVERTER_BACKUP_PROVIDER', 'local')
  backup_retention_count: int = int(os.getenv('CONVERTER_BACKUP_RETENTION', '10'))
  backup_remote_template: str = os.getenv('CONVERTER_BACKUP_TEMPLATE', '{project}/{direction}')

  def ensure_directories(self) -> None:
    self.data_dir.mkdir(parents=True, exist_ok=True)
    self.chroma_path.mkdir(parents=True, exist_ok=True)
    if not self.db_path.parent.exists():
      self.db_path.parent.mkdir(parents=True, exist_ok=True)
    self.secrets_dir.mkdir(parents=True, exist_ok=True)
    self.backup_root.mkdir(parents=True, exist_ok=True)
    if not self.secret_key_path.parent.exists():
      self.secret_key_path.parent.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_directories()
