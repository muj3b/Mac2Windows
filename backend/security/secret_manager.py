from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet


class SecretManager:
  """Manage encryption keys for credential storage."""

  def __init__(self, key_path: Path) -> None:
    self.key_path = Path(key_path)
    self.key_path.parent.mkdir(parents=True, exist_ok=True)
    self._fernet = Fernet(self._load_or_create_key())

  def _load_or_create_key(self) -> bytes:
    if self.key_path.exists():
      key = self.key_path.read_bytes().strip()
      if not key:
        raise ValueError(f'Encryption key file {self.key_path} is empty')
      return key
    key = Fernet.generate_key()
    with open(self.key_path, 'wb') as fh:
      fh.write(key)
    try:
      os.chmod(self.key_path, 0o600)
    except PermissionError:
      # On Windows chmod may fail; ignore as long as file exists.
      pass
    return key

  def encrypt(self, payload: bytes, associated_data: Optional[str] = None) -> bytes:
    """Encrypt payload bytes."""
    return self._fernet.encrypt(payload)

  def decrypt(self, token: bytes, associated_data: Optional[str] = None) -> bytes:
    """Decrypt token bytes."""
    return self._fernet.decrypt(token)
