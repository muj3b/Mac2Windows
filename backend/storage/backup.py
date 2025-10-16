from __future__ import annotations

import shutil
import time
from pathlib import Path
from typing import List


def create_backup(source: Path, backups_dir: Path, limit: int = 10) -> Path:
  backups_dir.mkdir(parents=True, exist_ok=True)
  timestamp = time.strftime('%Y%m%d_%H%M%S')
  archive_name = backups_dir / f'conversion_backup_{timestamp}'
  archive_path = shutil.make_archive(str(archive_name), 'zip', root_dir=source)
  _prune_old_backups(backups_dir, limit)
  return Path(archive_path)


def _prune_old_backups(backups_dir: Path, limit: int) -> None:
  archives = sorted(backups_dir.glob('conversion_backup_*.zip'), key=lambda p: p.stat().st_mtime, reverse=True)
  for archive in archives[limit:]:
    archive.unlink(missing_ok=True)
