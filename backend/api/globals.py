from backend.ai.provider_registry import ProviderRegistry
from backend.conversion.manager import ConversionManager
from backend.conversion.mappings import (
  DEPENDENCY_MAP,
  API_MAP,
  DependencyMapping,
  ApiMappingCatalog
)
from backend.config import settings
from backend.detection.scanner import ProjectScanner
from backend.resources.monitor import ResourceMonitor
from backend.storage.embeddings import EmbeddingStore
from backend.storage.state_store import StateStore
from backend.conversion.session_store import ConversionSessionStore
from backend.logging.event_logger import EventLogger
from backend.learning.memory import LearningMemory
from backend.templates.manager import TemplateManager
from backend.batch.manager import BatchManager
from backend.security.secret_manager import SecretManager
from backend.storage.credentials import CredentialStore
from backend.storage.backup import BackupManager

# Initialize globals
providers = ProviderRegistry()
scanner = ProjectScanner(settings=settings)
resources = ResourceMonitor()
state_store = StateStore(settings.db_path)
embedding_store = EmbeddingStore(settings.chroma_path)
session_store = ConversionSessionStore(settings.db_path)
event_logger = EventLogger(settings.data_dir / 'logs')
learning_memory = LearningMemory(settings.data_dir / 'learning_memory.json')
template_manager = TemplateManager(settings.data_dir / 'templates')
batch_manager = BatchManager()
secret_manager = SecretManager(settings.secret_key_path)
credential_store = CredentialStore(settings.credentials_db_path, secret_manager)
backup_manager = BackupManager(credential_store, settings.backup_root)
conversion_manager = ConversionManager(
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
