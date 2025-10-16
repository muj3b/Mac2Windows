from __future__ import annotations

import datetime
from pathlib import Path
from typing import Optional

import pygit2


class GitHandler:
  def __init__(self, repo_path: Path) -> None:
    self.repo_path = repo_path
    try:
      self.repo = pygit2.Repository(str(repo_path))
    except (KeyError, pygit2.GitError):
      try:
        self.repo = pygit2.init_repository(str(repo_path), initial_head='main')
      except pygit2.GitError:
        self.repo = None

  def commit_snapshot(self, message: str) -> Optional[str]:
    if not self.repo:
      return None
    index = self.repo.index
    index.add_all()
    index.write()
    tree = index.write_tree()
    if self.repo.head_is_unborn:
      author = pygit2.Signature('Converter', 'converter@example.com')
      commit = self.repo.create_commit('HEAD', author, author, message, tree, [])
    else:
      parent = self.repo.revparse_single('HEAD')
      author = pygit2.Signature('Converter', 'converter@example.com')
      commit = self.repo.create_commit('HEAD', author, author, message, tree, [parent.oid])
    return str(commit)

  def tag(self, name: str, message: str) -> Optional[str]:
    if not self.repo:
      return None
    commit = self.repo.revparse_single('HEAD')
    signature = pygit2.Signature('Converter', 'converter@example.com')
    tag = self.repo.create_tag(name, commit.oid, pygit2.GIT_OBJ_COMMIT, signature, message)
    return str(tag)
