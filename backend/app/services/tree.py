"""
Repository file-tree construction.

Turns a flat list of file paths into the nested ``FileNode`` structure the
frontend renders, with directories first and case-insensitive alphabetical
ordering at every level.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from app.schemas.repository import FileNode
from app.services.language import detect_language


def build_file_tree(entries: Iterable[Mapping[str, Any]]) -> list[FileNode]:
    """
    Build a nested tree.

    ``entries`` is any iterable of mappings containing at least ``file_path``;
    ``size_bytes`` and ``language`` are used when present.
    """
    root: dict[str, Any] = {}

    for entry in entries:
        path = str(entry.get("file_path", "")).strip("/")
        if not path:
            continue

        parts = path.split("/")
        cursor = root
        for part in parts[:-1]:
            node = cursor.setdefault(part, {"__children__": {}})
            cursor = node["__children__"]

        cursor[parts[-1]] = {
            "__file__": True,
            "path": path,
            "size": int(entry.get("size_bytes") or 0),
            "language": entry.get("language") or detect_language(path),
        }

    return _render(root, prefix="")


def _render(level: dict[str, Any], prefix: str) -> list[FileNode]:
    directories: list[FileNode] = []
    files: list[FileNode] = []

    for name, payload in level.items():
        path = f"{prefix}{name}"
        if payload.get("__file__"):
            files.append(
                FileNode(
                    name=name,
                    path=path,
                    type="blob",
                    size=payload.get("size"),
                    language=payload.get("language"),
                )
            )
        else:
            directories.append(
                FileNode(
                    name=name,
                    path=path,
                    type="tree",
                    children=_render(payload["__children__"], prefix=f"{path}/"),
                )
            )

    directories.sort(key=lambda n: n.name.lower())
    files.sort(key=lambda n: n.name.lower())
    return directories + files


def flatten_paths(nodes: list[FileNode]) -> list[str]:
    """Return every blob path in a tree (used by tests and the CLI)."""
    paths: list[str] = []
    for node in nodes:
        if node.type == "blob":
            paths.append(node.path)
        elif node.children:
            paths.extend(flatten_paths(node.children))
    return paths


__all__ = ["build_file_tree", "flatten_paths"]
