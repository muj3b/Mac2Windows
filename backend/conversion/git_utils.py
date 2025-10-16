from __future__ import annotations

import datetime
from pathlib import Path
from typing import Optional

import pygit2


class GitHandler:
  def __init__(self, repo_path: Path, branch: Optional[str] = None) -> None:
    self.repo_path = repo_path
    self.repo = None
    self.branch = branch
    try:
      self.repo = pygit2.Repository(str(repo_path))
    except (KeyError, pygit2.GitError):
      try:
        self.repo = pygit2.init_repository(str(repo_path), False)
      except pygit2.GitError:
        self.repo = None
    if self.repo and branch:
      try:
        self.repo.set_head(f'refs/heads/{branch}')
      except KeyError:
        pass

  def commit_snapshot(self, message: str) -> Optional[str]:
    if not self.repo:
      return None
    index = self.repo.index
    index.add_all()
    index.write()
    tree = index.write_tree()
    author = pygit2.Signature('Converter', 'converter@example.com')
    if self.repo.head_is_unborn:
      commit = self.repo.create_commit('HEAD', author, author, message, tree, [])
    else:
      parent = self.repo.revparse_single('HEAD')
      commit = self.repo.create_commit('HEAD', author, author, message, tree, [parent.oid])
    if self.branch and self.repo:
      refname = f'refs/heads/{self.branch}'
      try:
        self.repo.lookup_reference(refname)
      except KeyError:
        self.repo.create_reference(refname, commit)
      self.repo.set_head(refname)
    return str(commit)

  def tag(self, name: str, message: str) -> Optional[str]:
    if not self.repo:
      return None
    commit = self.repo.revparse_single('HEAD')
    signature = pygit2.Signature('Converter', 'converter@example.com')
    tag = self.repo.create_tag(name, commit.oid, pygit2.GIT_OBJ_COMMIT, signature, message)
    return str(tag)
