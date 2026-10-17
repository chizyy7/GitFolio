"""
GitFolio version-control engine — real Git object storage via ``pygit2``.

Design notes
------------
* Every repository gets its own on-disk Git object database under
  ``settings.STORAGE_PATH/<user_id>/<repo_id>``.  We never check files out;
  the object database is used purely for **hashing, tree construction and
  history**, while the authoritative "current file contents" live in
  PostgreSQL (``files`` table).  That keeps the DB the single source of truth
  for content and Git the single source of truth for identity/history.
* Commit identifiers are genuine Git SHA-1s, so ``git cat-file`` works against
  exported repositories.
* Diffs are produced with :mod:`difflib` from the old/new content maps.  This
  is deliberate: libgit2's patch generation needs a working directory, and
  difflib gives us deterministic line numbers that the AI reviewer relies on.
"""

from __future__ import annotations

import difflib
import hashlib
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pygit2

from app.core.config import settings
from app.core.logging import get_logger
from app.models.enums import ChangeType
from app.services.language import is_binary_bytes

logger = get_logger("vcs")

DEFAULT_BRANCH = "main"


# --------------------------------------------------------------------------- #
# Data structures
# --------------------------------------------------------------------------- #
@dataclass(slots=True)
class Author:
    """Who is committing."""

    name: str
    email: str


@dataclass(slots=True)
class DiffEntry:
    """A single changed file inside a commit."""

    path: str
    change_type: ChangeType
    old_content: str = ""
    new_content: str = ""
    diff_text: str = ""
    additions: int = 0
    deletions: int = 0
    blob_hash: str = ""

    @property
    def is_binary(self) -> bool:
        return is_binary_bytes(self.new_content.encode("utf-8", "replace")[:4096]) if self.new_content else False


@dataclass(slots=True)
class CommitResult:
    """Everything the API layer needs after a successful commit."""

    commit_hash: str
    short_hash: str
    message: str
    parent_hash: str | None
    diffs: list[DiffEntry] = field(default_factory=list)
    tree_oid: str = ""

    @property
    def files_changed(self) -> int:
        return len(self.diffs)

    @property
    def additions(self) -> int:
        return sum(d.additions for d in self.diffs)

    @property
    def deletions(self) -> int:
        return sum(d.deletions for d in self.diffs)

    @property
    def unified_diff(self) -> str:
        """Concatenated unified diff — what the AI reviewer consumes."""
        return "".join(d.diff_text for d in self.diffs)


# --------------------------------------------------------------------------- #
# Low-level helpers
# --------------------------------------------------------------------------- #
def compute_git_blob_hash(content: bytes) -> str:
    """
    Compute the SHA-1 of a Git *blob* object.

    Git hashes ``b"blob <len>\\0" + content``; this matches ``git hash-object``.
    """
    header = f"blob {len(content)}\0".encode("ascii")
    return hashlib.sha1(header + content).hexdigest()


def normalize_commit_message(message: str) -> str:
    """Git-style message normalisation (trailing newline, stripped edges)."""
    cleaned = (message or "").strip()
    if not cleaned:
        cleaned = "Update files"
    return cleaned + "\n"


def build_unified_diff(path: str, old: str, new: str, context: int = 3) -> tuple[str, int, int]:
    """
    Return ``(unified_diff_text, additions, deletions)`` for one file.

    The header uses ``a/`` and ``b/`` prefixes and ``new file mode``-style
    markers so the output is close enough to ``git diff`` for display.
    """
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)

    header: list[str] = []
    if not old and new:
        header.append(f"diff --git a/{path} b/{path}\n")
        header.append("new file mode 100644\n")
    elif old and not new:
        header.append(f"diff --git a/{path} b/{path}\n")
        header.append("deleted file mode 100644\n")
    else:
        header.append(f"diff --git a/{path} b/{path}\n")

    body = list(
        difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            n=context,
            lineterm="\n",
        )
    )
    # difflib emits headers without a trailing newline; normalise them.
    body = [line if line.endswith("\n") else line + "\n" for line in body]

    additions = sum(1 for line in body if line.startswith("+") and not line.startswith("+++"))
    deletions = sum(1 for line in body if line.startswith("-") and not line.startswith("---"))

    return "".join(header + body), additions, deletions


# --------------------------------------------------------------------------- #
# Engine
# --------------------------------------------------------------------------- #
class GitEngine:
    """
    Thin, safe wrapper around one ``pygit2.Repository``.

    Usage::

        engine = GitEngine.for_repo(user_id, repo_id)
        result = engine.commit(files={"app.py": "print('hi')"}, message="feat: init")
    """

    def __init__(self, repo_path: Path, branch: str = DEFAULT_BRANCH) -> None:
        self.path = Path(repo_path)
        self.branch = branch
        self.repo = self._open_or_init()

    # ---------------------------------------------------------------- setup
    @classmethod
    def for_repo(cls, user_id: str, repo_id: str, branch: str = DEFAULT_BRANCH) -> "GitEngine":
        """Resolve the canonical on-disk location for a repository."""
        repo_path = Path(settings.repos_root) / str(user_id) / str(repo_id)
        repo_path.mkdir(parents=True, exist_ok=True)
        return cls(repo_path, branch=branch)

    def _open_or_init(self) -> pygit2.Repository:
        git_dir = self.path / ".git"
        if git_dir.exists():
            return pygit2.Repository(str(self.path))

        logger.info("Initialising Git object database at %s", self.path)
        try:
            repo = pygit2.init_repository(
                str(self.path), bare=False, initial_head=self.branch
            )
        except TypeError:  # pragma: no cover - older pygit2
            repo = pygit2.init_repository(str(self.path), bare=False)
        # Disable GPG signing / hooks interference.
        try:
            repo.config["core.autocrlf"] = "false"
            repo.config["core.safecrlf"] = "false"
        except Exception:  # pragma: no cover
            pass
        return repo

    # ------------------------------------------------------------- refs
    @property
    def ref_name(self) -> str:
        return f"refs/heads/{self.branch}"

    def head_oid(self) -> pygit2.Oid | None:
        """OID of the tip commit, or ``None`` for an unborn branch."""
        try:
            return self.repo.head.target if not self.repo.head_is_unborn else None
        except Exception:
            return None

    def head_commit(self) -> pygit2.Commit | None:
        oid = self.head_oid()
        return self.repo[oid] if oid else None

    # ---------------------------------------------------------- tree I/O
    def _walk_tree(self, tree: pygit2.Tree, prefix: str = "") -> dict[str, str]:
        """Recursively flatten a tree into ``{path: content}`` (text only)."""
        files: dict[str, str] = {}
        for entry in tree:
            path = f"{prefix}{entry.name}"
            obj = self.repo[entry.id]
            if isinstance(obj, pygit2.Tree):
                files.update(self._walk_tree(obj, prefix=f"{path}/"))
            elif isinstance(obj, pygit2.Blob):
                data = bytes(obj.data)
                files[path] = "" if is_binary_bytes(data) else data.decode("utf-8", errors="replace")
        return files

    def files_at_head(self) -> dict[str, str]:
        """``{path: content}`` for the whole tree at HEAD."""
        commit = self.head_commit()
        if commit is None:
            return {}
        return self._walk_tree(commit.tree)

    def read_blob(self, path: str, ref: str = "HEAD") -> str | None:
        """Read one file's content at a ref (``None`` if absent)."""
        try:
            commit = self.repo.revparse_single(ref)
            entry = commit.tree / path if hasattr(commit.tree, "__truediv__") else None
            if entry is None:
                return None
            blob = self.repo[entry.id]
            return bytes(blob.data).decode("utf-8", errors="replace")
        except Exception:
            return None

    # ----------------------------------------------------------- commits
    def _write_tree(self, files: dict[str, str]) -> pygit2.Oid:
        """Stage ``files`` into the index and write a tree object."""
        index = self.repo.index
        index.clear()

        for path, content in sorted(files.items()):
            data = content.encode("utf-8", "replace")
            oid = self.repo.create_blob(data)
            index.add(pygit2.IndexEntry(path, oid, pygit2.GIT_FILEMODE_BLOB))

        index.write()
        return index.write_tree()

    def diff_against(
        self,
        new_files: dict[str, str],
        old_files: dict[str, str],
        deleted: set[str] | None = None,
    ) -> list[DiffEntry]:
        """Compute the file-level diff between two content maps."""
        deleted = deleted or set()
        entries: list[DiffEntry] = []

        all_paths = sorted(set(old_files) | set(new_files) | deleted - {""})
        for path in all_paths:
            old = old_files.get(path, "")
            new = new_files.get(path, "")

            if path in deleted and path in old_files:
                change = ChangeType.DELETED
                new = ""
            elif path not in old_files and path in new_files:
                change = ChangeType.ADDED
            elif old != new:
                change = ChangeType.MODIFIED
            else:
                continue  # untouched

            diff_text, additions, deletions = build_unified_diff(path, old, new)
            entries.append(
                DiffEntry(
                    path=path,
                    change_type=change,
                    old_content=old,
                    new_content=new,
                    diff_text=diff_text,
                    additions=additions,
                    deletions=deletions,
                    blob_hash=compute_git_blob_hash(new.encode("utf-8", "replace")),
                )
            )
        return entries

    def commit(
        self,
        files: dict[str, str],
        message: str,
        author: Author,
        deleted: list[str] | None = None,
        timestamp: datetime | None = None,
        allow_empty: bool = False,
    ) -> CommitResult:
        """
        Create a commit.

        ``files`` is the **full desired state** of the paths being pushed
        (unlisted paths keep their previous content).  Raises ``ValueError``
        when nothing changed and ``allow_empty`` is false.
        """
        old_files = self.files_at_head()
        deleted_set = set(deleted or [])
        new_files = dict(old_files)
        new_files.update(files)
        for path in deleted_set:
            new_files.pop(path, None)

        diffs = self.diff_against(new_files, old_files, deleted_set)
        if not diffs and not allow_empty:
            raise ValueError("Nothing to commit — the pushed files are identical to HEAD.")

        tree_oid = self._write_tree(new_files)

        ts = timestamp or datetime.now(timezone.utc)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        signature = pygit2.Signature(
            author.name, author.email, int(ts.timestamp()), 0
        )

        parent_commit = self.head_commit()
        parents = [parent_commit.id] if parent_commit is not None else []

        normalized = normalize_commit_message(message)
        oid = self.repo.create_commit(
            self.ref_name,
            signature,
            signature,
            normalized,
            tree_oid,
            parents,
        )

        # Make sure HEAD follows the branch we just wrote to (first commit case).
        if not parents:
            try:
                self.repo.set_head(self.ref_name)
            except Exception:  # pragma: no cover
                pass

        result = CommitResult(
            commit_hash=str(oid),
            short_hash=str(oid)[:7],
            message=normalized.strip(),
            parent_hash=str(parent_commit.id) if parent_commit else None,
            diffs=diffs,
            tree_oid=str(tree_oid),
        )
        logger.info(
            "Commit %s created in %s (%d files, +%d/-%d)",
            result.short_hash,
            self.path.name,
            result.files_changed,
            result.additions,
            result.deletions,
        )
        return result

    # ---------------------------------------------------------- lifecycle
    def delete(self) -> None:
        """Remove the on-disk object database (called when a repo is deleted)."""
        if self.path.exists():
            shutil.rmtree(self.path, ignore_errors=True)
            logger.info("Removed Git object database at %s", self.path)


# --------------------------------------------------------------------------- #
# Convenience
# --------------------------------------------------------------------------- #
def engine_for(repo_id: str, user_id: str, branch: str = DEFAULT_BRANCH) -> GitEngine:
    """Module-level factory used by the API layer."""
    return GitEngine.for_repo(user_id=user_id, repo_id=repo_id, branch=branch)


__all__ = [
    "Author",
    "CommitResult",
    "DiffEntry",
    "GitEngine",
    "build_unified_diff",
    "compute_git_blob_hash",
    "engine_for",
    "normalize_commit_message",
]
