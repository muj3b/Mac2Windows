from __future__ import annotations

import json
import logging
import os
import shutil
import time
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

from backend.conversion.models import BackupSettings
from backend.storage.credentials import BackupRecord, CredentialRecord, CredentialStore

logger = logging.getLogger(__name__)

EXCLUDED_DIRS = {'backups', '.git', '.svn', '.hg', '__pycache__', '.idea', '.vscode'}
EXCLUDED_FILES = {'.DS_Store'}


@dataclass
class BackupUploadResult:
  provider: str
  remote_id: Optional[str] = None
  remote_url: Optional[str] = None
  extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BackupResult:
  archive_path: Path
  metadata_path: Path
  metadata: Dict[str, Any]
  uploaded: Optional[BackupUploadResult] = None
  created_at: float = field(default_factory=time.time)


class BackupProvider:
  provider_id: str = 'base'
  display_name: str = 'Base Provider'
  requires_oauth: bool = False
  description: str = ''
  default_scopes: List[str] = []

  def describe(self) -> Dict[str, Any]:
    return {
      'id': self.provider_id,
      'name': self.display_name,
      'requires_oauth': self.requires_oauth,
      'description': self.description,
      'scopes': self.default_scopes
    }

  def upload(
    self,
    archive_path: Path,
    metadata_path: Path,
    metadata: Dict[str, Any],
    remote_subdir: str,
    credential: Optional[CredentialRecord]
  ) -> BackupUploadResult:
    raise NotImplementedError

  def delete(
    self,
    remote_id: str,
    remote_subdir: str,
    credential: Optional[CredentialRecord]
  ) -> None:
    raise NotImplementedError

  def build_oauth_request(
    self,
    payload: Dict[str, Any],
    redirect_uri: str
  ) -> Tuple[str, str, Dict[str, Any]]:
    raise NotImplementedError('Provider does not support OAuth onboarding')

  def exchange_oauth_code(
    self,
    state: str,
    code: str,
    redirect_uri: str,
    session_data: Dict[str, Any]
  ) -> CredentialRecord:
    raise NotImplementedError('Provider does not support OAuth onboarding')


class LocalBackupProvider(BackupProvider):
  provider_id = 'local'
  display_name = 'Local Disk'
  description = 'Stores backup archives on the local filesystem (configurable root).'

  def __init__(self, base_dir: Path) -> None:
    self.base_dir = Path(base_dir)
    self.base_dir.mkdir(parents=True, exist_ok=True)

  def upload(
    self,
    archive_path: Path,
    metadata_path: Path,
    metadata: Dict[str, Any],
    remote_subdir: str,
    credential: Optional[CredentialRecord]
  ) -> BackupUploadResult:
    target_root = self.base_dir
    if credential and credential.data.get('base_path'):
      target_root = Path(credential.data['base_path']).expanduser()
      target_root.mkdir(parents=True, exist_ok=True)
    destination_dir = (target_root / remote_subdir.strip('/'))
    destination_dir.mkdir(parents=True, exist_ok=True)

    dest_archive = destination_dir / archive_path.name
    dest_metadata = destination_dir / metadata_path.name
    shutil.copy2(archive_path, dest_archive)
    shutil.copy2(metadata_path, dest_metadata)
    return BackupUploadResult(
      provider=self.provider_id,
      remote_id=str(dest_archive.resolve()),
      remote_url=str(dest_archive.resolve()),
      extra={'metadata_path': str(dest_metadata.resolve())}
    )

  def delete(
    self,
    remote_id: str,
    remote_subdir: str,
    credential: Optional[CredentialRecord]
  ) -> None:
    archive_path = Path(remote_id)
    metadata_path = archive_path.with_suffix('.json')
    try:
      archive_path.unlink(missing_ok=True)
      metadata_path.unlink(missing_ok=True)
    except OSError as exc:
      logger.warning('Failed to remove local backup %s: %s', archive_path, exc)


class GoogleDriveProvider(BackupProvider):
  provider_id = 'google_drive'
  display_name = 'Google Drive'
  requires_oauth = True
  description = 'Uploads archives to Google Drive using Drive API v3.'
  default_scopes = ['https://www.googleapis.com/auth/drive.file']
  AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
  TOKEN_URL = 'https://oauth2.googleapis.com/token'
  FILES_URL = 'https://www.googleapis.com/drive/v3/files'
  UPLOAD_URL = 'https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id,webViewLink'

  def __init__(self, store: CredentialStore) -> None:
    self.store = store

  def upload(
    self,
    archive_path: Path,
    metadata_path: Path,
    metadata: Dict[str, Any],
    remote_subdir: str,
    credential: Optional[CredentialRecord]
  ) -> BackupUploadResult:
    if not credential:
      raise ValueError('Google Drive upload requires linked credentials.')
    credential = self._ensure_token_fresh(credential)
    token = credential.data['access_token']
    folder_id = self._ensure_remote_folder(token, credential, remote_subdir)

    headers = {'Authorization': f"Bearer {token}"}
    app_properties = {
      'converterSession': metadata['session_id'],
      'converterDirection': metadata['direction']
    }
    file_metadata = {
      'name': archive_path.name,
      'parents': [folder_id],
      'description': json.dumps({
        'project': metadata['project_name'],
        'created_at': metadata['created_at']
      }),
      'appProperties': app_properties
    }

    with archive_path.open('rb') as archive_file:
      files = {
        'metadata': ('metadata', json.dumps(file_metadata), 'application/json; charset=UTF-8'),
        'file': (archive_path.name, archive_file, 'application/zip')
      }
      response = requests.post(self.UPLOAD_URL, headers=headers, files=files, timeout=120)
    response.raise_for_status()
    payload = response.json()
    remote_id = payload['id']
    web_view = payload.get('webViewLink')
    backup_result = BackupUploadResult(
      provider=self.provider_id,
      remote_id=remote_id,
      remote_url=web_view,
      extra={'folder_id': folder_id}
    )

    with metadata_path.open('rb') as meta_file:
      meta_payload = {
        'name': metadata_path.name,
        'parents': [folder_id]
      }
      files = {
        'metadata': ('metadata', json.dumps(meta_payload), 'application/json; charset=UTF-8'),
        'file': (metadata_path.name, meta_file, 'application/json')
      }
      meta_response = requests.post(self.UPLOAD_URL, headers=headers, files=files, timeout=60)
    meta_response.raise_for_status()
    backup_result.extra['metadata_file_id'] = meta_response.json().get('id')
    return backup_result

  def delete(
    self,
    remote_id: str,
    remote_subdir: str,
    credential: Optional[CredentialRecord]
  ) -> None:
    if not credential:
      return
    credential = self._ensure_token_fresh(credential)
    token = credential.data['access_token']
    response = requests.delete(f'{self.FILES_URL}/{remote_id}', headers={'Authorization': f'Bearer {token}'}, timeout=30)
    if response.status_code not in (204, 200):
      logger.warning('Failed to delete Google Drive file %s: %s', remote_id, response.text)

  def build_oauth_request(
    self,
    payload: Dict[str, Any],
    redirect_uri: str
  ) -> Tuple[str, str, Dict[str, Any]]:
    client_id = payload.get('client_id')
    client_secret = payload.get('client_secret')
    label = payload.get('label')
    if not client_id or not client_secret or not label:
      raise ValueError('client_id, client_secret, and label are required for Google Drive OAuth.')
    scopes = payload.get('scopes') or self.default_scopes
    state = uuid.uuid4().hex
    params = {
      'client_id': client_id,
      'redirect_uri': redirect_uri,
      'response_type': 'code',
      'scope': ' '.join(scopes),
      'state': state,
      'access_type': 'offline',
      'prompt': 'consent'
    }
    auth_url = f"{self.AUTH_URL}?{requests.compat.urlencode(params)}"
    session_data = {
      'client_id': client_id,
      'client_secret': client_secret,
      'scopes': scopes,
      'label': label,
      'root_folder': payload.get('root_folder', 'MacWinConverter Backups')
    }
    return state, auth_url, session_data

  def exchange_oauth_code(
    self,
    state: str,
    code: str,
    redirect_uri: str,
    session_data: Dict[str, Any]
  ) -> CredentialRecord:
    data = {
      'code': code,
      'client_id': session_data['client_id'],
      'client_secret': session_data['client_secret'],
      'redirect_uri': redirect_uri,
      'grant_type': 'authorization_code'
    }
    response = requests.post(self.TOKEN_URL, data=data, timeout=60)
    response.raise_for_status()
    payload = response.json()
    refresh_token = payload.get('refresh_token')
    access_token = payload.get('access_token')
    expires_in = payload.get('expires_in', 3600)
    if not refresh_token or not access_token:
      raise ValueError('Google token exchange did not return refresh/access tokens.')
    credential_payload = {
      'client_id': session_data['client_id'],
      'client_secret': session_data['client_secret'],
      'access_token': access_token,
      'refresh_token': refresh_token,
      'expires_at': time.time() + float(expires_in) - 60,
      'scopes': session_data['scopes'],
      'root_folder': session_data.get('root_folder', 'MacWinConverter Backups')
    }
    return self.store.save_credentials(self.provider_id, session_data['label'], credential_payload)

  def _ensure_token_fresh(self, credential: CredentialRecord) -> CredentialRecord:
    expires_at = credential.data.get('expires_at', 0)
    if time.time() < expires_at:
      return credential
    data = {
      'client_id': credential.data['client_id'],
      'client_secret': credential.data['client_secret'],
      'refresh_token': credential.data['refresh_token'],
      'grant_type': 'refresh_token'
    }
    response = requests.post(self.TOKEN_URL, data=data, timeout=60)
    response.raise_for_status()
    payload = response.json()
    credential.data['access_token'] = payload['access_token']
    credential.data['expires_at'] = time.time() + float(payload.get('expires_in', 3600)) - 60
    updated = self.store.update_credentials(credential.id, credential.data)
    return updated or credential

  def _ensure_remote_folder(self, token: str, credential: CredentialRecord, remote_subdir: str) -> str:
    root_id = credential.data.get('root_folder_id')
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    if not root_id:
      root_name = credential.data.get('root_folder', 'MacWinConverter Backups')
      root_id = self._ensure_child_folder(headers, 'root', root_name)
      credential.data['root_folder_id'] = root_id
      self.store.update_credentials(credential.id, credential.data)

    parent_id = root_id
    for segment in filter(None, remote_subdir.split('/')):
      parent_id = self._ensure_child_folder(headers, parent_id, segment)
    return parent_id

  def _ensure_child_folder(self, headers: Dict[str, str], parent_id: str, name: str) -> str:
    params = {
      'q': f"name='{name}' and '{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
      'fields': 'files(id, name)',
      'pageSize': 1
    }
    response = requests.get(self.FILES_URL, headers={'Authorization': headers['Authorization']}, params=params, timeout=30)
    response.raise_for_status()
    files = response.json().get('files', [])
    if files:
      return files[0]['id']
    payload = {
      'name': name,
      'mimeType': 'application/vnd.google-apps.folder',
      'parents': [parent_id]
    }
    create = requests.post(self.FILES_URL, headers=headers, data=json.dumps(payload), timeout=30)
    create.raise_for_status()
    return create.json()['id']


class DropboxProvider(BackupProvider):
  provider_id = 'dropbox'
  display_name = 'Dropbox'
  requires_oauth = True
  description = 'Uploads archives to Dropbox user accounts.'
  default_scopes = ['files.content.write', 'files.content.read']
  AUTH_URL = 'https://www.dropbox.com/oauth2/authorize'
  TOKEN_URL = 'https://api.dropboxapi.com/oauth2/token'
  UPLOAD_URL = 'https://content.dropboxapi.com/2/files/upload'
  DELETE_URL = 'https://api.dropboxapi.com/2/files/delete_v2'

  def __init__(self, store: CredentialStore) -> None:
    self.store = store

  def upload(
    self,
    archive_path: Path,
    metadata_path: Path,
    metadata: Dict[str, Any],
    remote_subdir: str,
    credential: Optional[CredentialRecord]
  ) -> BackupUploadResult:
    if not credential:
      raise ValueError('Dropbox upload requires linked credentials.')
    credential = self._ensure_token_fresh(credential)
    token = credential.data['access_token']
    dropbox_path = self._build_dropbox_path(credential, remote_subdir, archive_path.name)
    headers = {
      'Authorization': f'Bearer {token}',
      'Dropbox-API-Arg': json.dumps({
        'path': dropbox_path,
        'mode': 'overwrite',
        'mute': True,
        'strict_conflict': False
      }),
      'Content-Type': 'application/octet-stream'
    }
    with archive_path.open('rb') as archive_file:
      response = requests.post(self.UPLOAD_URL, headers=headers, data=archive_file.read(), timeout=120)
    response.raise_for_status()

    metadata_remote_path = self._build_dropbox_path(credential, remote_subdir, metadata_path.name)
    meta_headers = headers.copy()
    meta_headers['Dropbox-API-Arg'] = json.dumps({
      'path': metadata_remote_path,
      'mode': 'overwrite',
      'mute': True,
      'strict_conflict': False
    })
    with metadata_path.open('rb') as metadata_file:
      meta_response = requests.post(self.UPLOAD_URL, headers=meta_headers, data=metadata_file.read(), timeout=60)
    meta_response.raise_for_status()

    return BackupUploadResult(
      provider=self.provider_id,
      remote_id=dropbox_path,
      remote_url=None,
      extra={'metadata_path': metadata_remote_path}
    )

  def delete(
    self,
    remote_id: str,
    remote_subdir: str,
    credential: Optional[CredentialRecord]
  ) -> None:
    if not credential:
      return
    credential = self._ensure_token_fresh(credential)
    token = credential.data['access_token']
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    payload = {'path': remote_id}
    response = requests.post(self.DELETE_URL, headers=headers, data=json.dumps(payload), timeout=30)
    if response.status_code not in (200, 409):
      logger.warning('Failed to delete Dropbox file %s: %s', remote_id, response.text)

  def build_oauth_request(
    self,
    payload: Dict[str, Any],
    redirect_uri: str
  ) -> Tuple[str, str, Dict[str, Any]]:
    client_id = payload.get('client_id')
    client_secret = payload.get('client_secret')
    label = payload.get('label')
    if not client_id or not client_secret or not label:
      raise ValueError('client_id, client_secret, and label are required for Dropbox OAuth.')
    scopes = payload.get('scopes') or self.default_scopes
    state = uuid.uuid4().hex
    params = {
      'response_type': 'code',
      'client_id': client_id,
      'redirect_uri': redirect_uri,
      'state': state,
      'token_access_type': 'offline',
      'scope': ' '.join(scopes)
    }
    auth_url = f'{self.AUTH_URL}?{requests.compat.urlencode(params)}'
    session_data = {
      'client_id': client_id,
      'client_secret': client_secret,
      'label': label,
      'scopes': scopes,
      'root_folder': payload.get('root_folder', '/MacWinConverter')
    }
    return state, auth_url, session_data

  def exchange_oauth_code(
    self,
    state: str,
    code: str,
    redirect_uri: str,
    session_data: Dict[str, Any]
  ) -> CredentialRecord:
    data = {
      'code': code,
      'grant_type': 'authorization_code',
      'client_id': session_data['client_id'],
      'client_secret': session_data['client_secret'],
      'redirect_uri': redirect_uri
    }
    response = requests.post(self.TOKEN_URL, data=data, timeout=60)
    response.raise_for_status()
    payload = response.json()
    refresh_token = payload.get('refresh_token')
    access_token = payload.get('access_token')
    expires_in = payload.get('expires_in', 14400)
    if not refresh_token or not access_token:
      raise ValueError('Dropbox token exchange did not return refresh/access tokens.')
    credential_payload = {
      'client_id': session_data['client_id'],
      'client_secret': session_data['client_secret'],
      'access_token': access_token,
      'refresh_token': refresh_token,
      'expires_at': time.time() + float(expires_in) - 60,
      'scopes': session_data['scopes'],
      'root_folder': session_data.get('root_folder', '/MacWinConverter')
    }
    return self.store.save_credentials(self.provider_id, session_data['label'], credential_payload)

  def _ensure_token_fresh(self, credential: CredentialRecord) -> CredentialRecord:
    expires_at = credential.data.get('expires_at', 0)
    if time.time() < expires_at:
      return credential
    data = {
      'refresh_token': credential.data['refresh_token'],
      'grant_type': 'refresh_token',
      'client_id': credential.data['client_id'],
      'client_secret': credential.data['client_secret']
    }
    response = requests.post(self.TOKEN_URL, data=data, timeout=60)
    response.raise_for_status()
    payload = response.json()
    credential.data['access_token'] = payload['access_token']
    credential.data['expires_at'] = time.time() + float(payload.get('expires_in', 14400)) - 60
    updated = self.store.update_credentials(credential.id, credential.data)
    return updated or credential

  def _build_dropbox_path(self, credential: CredentialRecord, remote_subdir: str, filename: str) -> str:
    root = credential.data.get('root_folder', '/MacWinConverter')
    combined = '/'.join(segment.strip('/') for segment in (root, remote_subdir, filename) if segment)
    if not combined.startswith('/'):
      combined = '/' + combined
    return combined


class OneDriveProvider(BackupProvider):
  provider_id = 'one_drive'
  display_name = 'OneDrive'
  requires_oauth = True
  description = 'Stores archives in Microsoft OneDrive via Microsoft Graph.'
  default_scopes = ['offline_access', 'Files.ReadWrite.All']
  AUTH_URL_TEMPLATE = 'https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize'
  TOKEN_URL_TEMPLATE = 'https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token'
  GRAPH_ROOT = 'https://graph.microsoft.com/v1.0'

  def __init__(self, store: CredentialStore) -> None:
    self.store = store

  def upload(
    self,
    archive_path: Path,
    metadata_path: Path,
    metadata: Dict[str, Any],
    remote_subdir: str,
    credential: Optional[CredentialRecord]
  ) -> BackupUploadResult:
    if not credential:
      raise ValueError('OneDrive upload requires linked credentials.')
    credential = self._ensure_token_fresh(credential)
    token = credential.data['access_token']
    remote_path = self._build_remote_path(credential, remote_subdir, archive_path.name)
    headers = {'Authorization': f'Bearer {token}'}
    with archive_path.open('rb') as archive_file:
      response = requests.put(
        f'{self.GRAPH_ROOT}/me/drive/root:{remote_path}:/content',
        headers=headers,
        data=archive_file.read(),
        timeout=120
      )
    response.raise_for_status()
    remote_id = response.json().get('id')

    metadata_remote_path = self._build_remote_path(credential, remote_subdir, metadata_path.name)
    with metadata_path.open('rb') as metadata_file:
      meta_response = requests.put(
        f'{self.GRAPH_ROOT}/me/drive/root:{metadata_remote_path}:/content',
        headers=headers,
        data=metadata_file.read(),
        timeout=60
      )
    meta_response.raise_for_status()

    return BackupUploadResult(
      provider=self.provider_id,
      remote_id=remote_id,
      remote_url=response.json().get('@microsoft.graph.downloadUrl'),
      extra={'metadata_path': metadata_remote_path}
    )

  def delete(
    self,
    remote_id: str,
    remote_subdir: str,
    credential: Optional[CredentialRecord]
  ) -> None:
    if not credential:
      return
    credential = self._ensure_token_fresh(credential)
    token = credential.data['access_token']
    response = requests.delete(
      f'{self.GRAPH_ROOT}/me/drive/items/{remote_id}',
      headers={'Authorization': f'Bearer {token}'},
      timeout=30
    )
    if response.status_code not in (204, 200):
      logger.warning('Failed to delete OneDrive item %s: %s', remote_id, response.text)

  def build_oauth_request(
    self,
    payload: Dict[str, Any],
    redirect_uri: str
  ) -> Tuple[str, str, Dict[str, Any]]:
    client_id = payload.get('client_id')
    client_secret = payload.get('client_secret')
    label = payload.get('label')
    tenant = payload.get('tenant', 'common')
    if not client_id or not client_secret or not label:
      raise ValueError('client_id, client_secret, and label are required for OneDrive OAuth.')
    scopes = payload.get('scopes') or self.default_scopes
    state = uuid.uuid4().hex
    params = {
      'client_id': client_id,
      'scope': ' '.join(scopes),
      'response_type': 'code',
      'redirect_uri': redirect_uri,
      'state': state
    }
    auth_url = f"{self.AUTH_URL_TEMPLATE.format(tenant=tenant)}?{requests.compat.urlencode(params)}"
    session_data = {
      'client_id': client_id,
      'client_secret': client_secret,
      'label': label,
      'scopes': scopes,
      'tenant': tenant,
      'root_folder': payload.get('root_folder', 'MacWinConverter')
    }
    return state, auth_url, session_data

  def exchange_oauth_code(
    self,
    state: str,
    code: str,
    redirect_uri: str,
    session_data: Dict[str, Any]
  ) -> CredentialRecord:
    data = {
      'client_id': session_data['client_id'],
      'client_secret': session_data['client_secret'],
      'grant_type': 'authorization_code',
      'code': code,
      'redirect_uri': redirect_uri,
      'scope': ' '.join(session_data['scopes'])
    }
    token_url = self.TOKEN_URL_TEMPLATE.format(tenant=session_data['tenant'])
    response = requests.post(token_url, data=data, timeout=60)
    response.raise_for_status()
    payload = response.json()
    refresh_token = payload.get('refresh_token')
    access_token = payload.get('access_token')
    expires_in = payload.get('expires_in', 3600)
    if not refresh_token or not access_token:
      raise ValueError('OneDrive token exchange did not return refresh/access tokens.')
    credential_payload = {
      'client_id': session_data['client_id'],
      'client_secret': session_data['client_secret'],
      'tenant': session_data['tenant'],
      'access_token': access_token,
      'refresh_token': refresh_token,
      'expires_at': time.time() + float(expires_in) - 60,
      'scopes': session_data['scopes'],
      'root_folder': session_data.get('root_folder', 'MacWinConverter')
    }
    return self.store.save_credentials(self.provider_id, session_data['label'], credential_payload)

  def _ensure_token_fresh(self, credential: CredentialRecord) -> CredentialRecord:
    expires_at = credential.data.get('expires_at', 0)
    if time.time() < expires_at:
      return credential
    data = {
      'client_id': credential.data['client_id'],
      'client_secret': credential.data['client_secret'],
      'refresh_token': credential.data['refresh_token'],
      'grant_type': 'refresh_token',
      'scope': ' '.join(credential.data.get('scopes', self.default_scopes))
    }
    token_url = self.TOKEN_URL_TEMPLATE.format(tenant=credential.data.get('tenant', 'common'))
    response = requests.post(token_url, data=data, timeout=60)
    response.raise_for_status()
    payload = response.json()
    credential.data['access_token'] = payload['access_token']
    credential.data['expires_at'] = time.time() + float(payload.get('expires_in', 3600)) - 60
    updated = self.store.update_credentials(credential.id, credential.data)
    return updated or credential

  def _build_remote_path(self, credential: CredentialRecord, remote_subdir: str, filename: str) -> str:
    root = credential.data.get('root_folder', 'MacWinConverter')
    segments = [segment.strip('/') for segment in (root, remote_subdir, filename) if segment]
    path = '/' + '/'.join(segments)
    return path


class BackupManager:
  def __init__(self, credential_store: CredentialStore, local_root: Path) -> None:
    self.credential_store = credential_store
    self.local_root = Path(local_root)
    self.local_root.mkdir(parents=True, exist_ok=True)
    self.providers: Dict[str, BackupProvider] = {
      'local': LocalBackupProvider(self.local_root),
      'google_drive': GoogleDriveProvider(self.credential_store),
      'dropbox': DropboxProvider(self.credential_store),
      'one_drive': OneDriveProvider(self.credential_store)
    }
    self.oauth_sessions: Dict[str, Dict[str, Any]] = {}

  def list_providers(self) -> List[Dict[str, Any]]:
    providers: List[Dict[str, Any]] = []
    for provider_id, provider in self.providers.items():
      credentials = [
        {
          'id': record.id,
          'label': record.label,
          'created_at': record.created_at,
          'updated_at': record.updated_at
        }
        for record in self.credential_store.list_credentials(provider_id)
      ]
      info = provider.describe()
      info['credentials'] = credentials
      info['connected'] = bool(credentials)
      providers.append(info)
    return providers

  def start_oauth(self, provider_id: str, payload: Dict[str, Any], redirect_uri: str) -> Dict[str, Any]:
    provider = self._get_provider(provider_id)
    if not provider.requires_oauth:
      raise ValueError(f'Provider {provider_id} does not support OAuth onboarding.')
    state, auth_url, session_data = provider.build_oauth_request(payload, redirect_uri)
    session_data['redirect_uri'] = redirect_uri
    session_data['provider_id'] = provider_id
    self.oauth_sessions[state] = session_data
    return {'auth_url': auth_url, 'state': state}

  def complete_oauth(self, provider_id: str, state: str, code: str) -> CredentialRecord:
    session_data = self.oauth_sessions.pop(state, None)
    if not session_data:
      raise ValueError('OAuth state not found or expired.')
    if session_data.get('provider_id') != provider_id:
      raise ValueError('OAuth provider mismatch.')
    provider = self._get_provider(provider_id)
    redirect_uri = session_data['redirect_uri']
    credential = provider.exchange_oauth_code(
      state=state,
      code=code,
      redirect_uri=redirect_uri,
      session_data=session_data
    )
    logger.info('Stored credentials for provider %s (%s)', provider_id, credential.label)
    return credential

  def delete_credential(self, credential_id: str) -> bool:
    return self.credential_store.delete_credentials(credential_id)

  def create_backup(self, session, backup_settings: BackupSettings) -> BackupResult:
    metadata = self._build_metadata(session)
    archive_path, metadata_path = self._create_archive(session.target_path, metadata, backup_settings.retention_count)
    metadata['local_archive'] = str(archive_path)
    metadata['metadata_file'] = str(metadata_path)
    metadata['created_at'] = time.time()
    remote_result: Optional[BackupUploadResult] = None

    remote_subdir = self._render_remote_subdir(session, backup_settings)
    configured_provider = backup_settings.provider or 'local'
    provider_id = configured_provider if backup_settings.enabled else 'local'
    provider = self._get_provider(provider_id)
    credential: Optional[CredentialRecord] = None
    if backup_settings.credential_id:
      if backup_settings.enabled or provider_id == 'local':
        credential = self._resolve_credential(provider_id, backup_settings.credential_id)
    record_metadata = {
      **metadata,
      'remote_subdir': remote_subdir,
      'provider': provider_id,
      'configured_provider': configured_provider
    }

    if backup_settings.enabled:
      try:
        remote_result = provider.upload(archive_path, metadata_path, metadata, remote_subdir, credential)
        if remote_result:
          record_metadata['remote'] = {
            'remote_id': remote_result.remote_id,
            'remote_url': remote_result.remote_url,
            'extra': remote_result.extra
          }
      except Exception as exc:  # pragma: no cover - network/int
        logger.exception('Cloud backup upload failed: %s', exc)
        record_metadata['remote_error'] = str(exc)
    remote_id_value = remote_result.remote_id if remote_result else None
    remote_url_value = remote_result.remote_url if remote_result else None
    record = self.credential_store.record_backup(
      session_id=session.session_id,
      provider=provider_id,
      metadata=record_metadata,
      credential_id=backup_settings.credential_id,
      remote_id=remote_id_value,
      remote_url=remote_url_value
    )
    if backup_settings.retention_count > 0:
      self._prune_local(Path(session.target_path) / 'backups', backup_settings.retention_count)
      if remote_result:
        self._prune_remote(provider_id, backup_settings, credential)
    logger.info('Backup created for session %s at %s', session.session_id, archive_path)
    return BackupResult(
      archive_path=archive_path,
      metadata_path=metadata_path,
      metadata=record_metadata,
      uploaded=remote_result
    )

  def list_backups(self, session_id: Optional[str] = None) -> List[BackupRecord]:
    return self.credential_store.list_backups(session_id=session_id)

  def _prune_local(self, backups_dir: Path, limit: int) -> None:
    if limit < 1:
      return
    archives = sorted(backups_dir.glob('conversion_backup_*.zip'), key=lambda p: p.stat().st_mtime, reverse=True)
    for archive in archives[limit:]:
      metadata_file = archive.with_suffix('.json')
      try:
        archive.unlink(missing_ok=True)
        metadata_file.unlink(missing_ok=True)
        logger.debug('Pruned local backup %s', archive)
      except OSError as exc:
        logger.warning('Failed to prune local backup %s: %s', archive, exc)

  def _prune_remote(self, provider_id: str, backup_settings: BackupSettings, credential: Optional[CredentialRecord]) -> None:
    if backup_settings.retention_count < 1:
      return
    records = self.credential_store.list_backups(provider=provider_id, credential_id=backup_settings.credential_id)
    for record in records[backup_settings.retention_count:]:
      remote_id = record.remote_id
      if not remote_id:
        self.credential_store.delete_backup(record.id)
        continue
      try:
        provider = self._get_provider(provider_id)
        provider.delete(remote_id, record.metadata.get('remote_subdir', ''), credential)
      except Exception as exc:  # pragma: no cover - network/int
        logger.warning('Failed to prune remote backup %s/%s: %s', provider_id, remote_id, exc)
        continue
      self.credential_store.delete_backup(record.id)

  def _create_archive(self, target_path: Path, metadata: Dict[str, Any], retention_count: int) -> Tuple[Path, Path]:
    backups_dir = target_path / 'backups'
    backups_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime('%Y%m%d_%H%M%S')
    archive_name = f'conversion_backup_{timestamp}'
    archive_path = backups_dir / f'{archive_name}.zip'
    metadata_path = backups_dir / f'{archive_name}.json'

    with zipfile.ZipFile(archive_path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
      for path in target_path.rglob('*'):
        if self._should_skip(target_path, path):
          continue
        if path.is_file():
          arcname = path.relative_to(target_path).as_posix()
          zf.write(path, arcname)
      zf.writestr('conversion_metadata.json', json.dumps(metadata, indent=2))

    metadata_path.write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    return archive_path, metadata_path

  def _should_skip(self, root: Path, candidate: Path) -> bool:
    try:
      parts = candidate.relative_to(root).parts
    except ValueError:
      return True
    if any(part in EXCLUDED_DIRS for part in parts[:-1]):
      return True
    if candidate.name in EXCLUDED_FILES:
      return True
    return False

  def _build_metadata(self, session) -> Dict[str, Any]:
    summary = session.progress.summary()
    project_name = session.project_path.name
    metadata = {
      'session_id': session.session_id,
      'direction': session.direction,
      'project_name': project_name,
      'project_path': str(session.project_path),
      'target_path': str(session.target_path),
      'converted_files': summary.converted_files,
      'total_files': summary.total_files,
      'tokens_used': summary.tokens_used,
      'cost_usd': summary.cost_usd,
      'elapsed_seconds': summary.elapsed_seconds,
      'manual_fixes_pending': getattr(summary, 'manual_fixes_pending', 0),
      'notes': session.summary_notes,
      'quality': session.quality_report.summary() if session.quality_report else None
    }
    return metadata

  def _render_remote_subdir(self, session, backup_settings: BackupSettings) -> str:
    template = backup_settings.remote_path or '{project}/{direction}'
    context = {
      'project': session.project_path.name,
      'direction': session.direction,
      'session': session.session_id,
      'timestamp': time.strftime('%Y%m%d')
    }
    try:
      rendered = template.format(**context)
    except KeyError:
      rendered = template
    return rendered.strip('/')

  def _resolve_credential(self, provider_id: str, credential_id: Optional[str]) -> Optional[CredentialRecord]:
    if not credential_id:
      return None
    record = self.credential_store.get_credentials(credential_id)
    if not record:
      raise ValueError(f'Credential {credential_id} not found for provider {provider_id}.')
    if record.provider != provider_id:
      raise ValueError('Credential provider mismatch.')
    return record

  def _get_provider(self, provider_id: str) -> BackupProvider:
    try:
      return self.providers[provider_id]
    except KeyError as exc:
      raise ValueError(f'Unknown backup provider: {provider_id}') from exc
