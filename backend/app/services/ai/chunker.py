"""
Tree-sitter based code chunker.

Rationale: naïvely splitting source files every N characters produces
embeddings that straddle function boundaries and retrieve terribly.  Parsing
the AST lets us emit **whole functions and classes** as chunks, so a retrieval
hit is always something a developer can actually read.

Supported grammars: Python, JavaScript, TypeScript/TSX.
Everything else falls back to a sliding line-window strategy that still
respects blank-line boundaries and a maximum size.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger
from app.services.language import detect_language

logger = get_logger("chunker")


# --------------------------------------------------------------------------- #
# Chunk model
# --------------------------------------------------------------------------- #
@dataclass(slots=True)
class CodeChunk:
    """One embeddable unit of source code."""

    file_path: str
    language: str
    content: str
    start_line: int  # 1-based, inclusive
    end_line: int  # 1-based, inclusive
    symbol: str | None = None
    kind: str = "module"  # function | class | method | module | window
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def text_for_embedding(self) -> str:
        """
        The exact string we embed.

        A short header gives the embedding model (and the LLM) the path and
        symbol context — measurably better retrieval than raw code alone.
        """
        header = f"# File: {self.file_path} ({self.language})"
        if self.symbol:
            header += f"\n# {self.kind.capitalize()}: {self.symbol}"
        header += f"\n# Lines: {self.start_line}-{self.end_line}\n\n"
        return header + self.content


# --------------------------------------------------------------------------- #
# Grammar loading
# --------------------------------------------------------------------------- #
# language -> (importable module, attribute holding the grammar factory).
# ``tree-sitter-python`` / ``tree-sitter-javascript`` expose ``language`` while
# ``tree-sitter-typescript`` exposes ``language_typescript`` / ``language_tsx``.
_GRAMMAR_MODULES: dict[str, tuple[str, str]] = {
    "Python": ("tree_sitter_python", "language"),
    "JavaScript": ("tree_sitter_javascript", "language"),
    "JSX": ("tree_sitter_javascript", "language"),
    "TypeScript": ("tree_sitter_typescript", "language_typescript"),
    "TSX": ("tree_sitter_typescript", "language_tsx"),
}


@lru_cache(maxsize=8)
def _load_parser(language: str) -> Any | None:
    """Return a configured tree-sitter ``Parser`` or ``None`` if unsupported."""
    grammar = _GRAMMAR_MODULES.get(language)
    if grammar is None:
        return None

    module_name, attribute = grammar

    try:
        from tree_sitter import Language, Parser

        module = __import__(module_name)
        raw = getattr(module, attribute)
        raw = raw() if callable(raw) else raw
        parser = Parser(Language(raw))  # tree-sitter >= 0.22
        return parser
    except Exception as exc:  # pragma: no cover - optional dependency
        logger.debug("No tree-sitter grammar for %s (%s); using fallback", language, exc)
        return None


# Node types that represent a logical, self-contained unit.
_PYTHON_SYMBOL_NODES = {
    "function_definition",
    "class_definition",
    "decorated_definition",
}

# JavaScript/JSX/TypeScript/TSX share (nearly) the same symbol grammar; extra
# node types that do not exist in a given dialect are simply never matched.
_SCRIPT_SYMBOL_NODES = {
    "function_declaration",
    "generator_function_declaration",
    "class_declaration",
    "method_definition",
    "lexical_declaration",
    "export_statement",
    "interface_declaration",
    "type_alias_declaration",
    "enum_declaration",
}

_SYMBOL_NODES: dict[str, set[str]] = {
    "Python": _PYTHON_SYMBOL_NODES,
    "JavaScript": _SCRIPT_SYMBOL_NODES,
    "JSX": _SCRIPT_SYMBOL_NODES,
    "TypeScript": _SCRIPT_SYMBOL_NODES,
    "TSX": _SCRIPT_SYMBOL_NODES,
}

_KIND_BY_NODE = {
    "function_definition": "function",
    "function_declaration": "function",
    "generator_function_declaration": "function",
    "class_definition": "class",
    "class_declaration": "class",
    "method_definition": "method",
    "interface_declaration": "interface",
    "type_alias_declaration": "type",
    "enum_declaration": "enum",
    "lexical_declaration": "variable",
    "export_statement": "export",
    "decorated_definition": "function",
}


def _node_text(source: bytes, node: Any) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _node_name(node: Any) -> str | None:
    """Extract the declared name of a symbol node, if any."""
    try:
        name_node = node.child_by_field_name("name")
        if name_node is not None:
            return name_node.text.decode("utf-8", errors="replace")
        # `export function foo()` / `@decorator\ndef foo()` -> look one level down.
        for child in node.children:
            if child.type in ("function_definition", "class_definition") or child.is_named:
                inner = child.child_by_field_name("name")
                if inner is not None:
                    return inner.text.decode("utf-8", errors="replace")
        # `const handler = () => {}`
        decl = node.child_by_field_name("declarator")
        if decl is not None:
            ident = decl.child_by_field_name("name")
            if ident is not None:
                return ident.text.decode("utf-8", errors="replace")
    except Exception:  # pragma: no cover
        return None
    return None


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def chunk_file(file_path: str, content: str, *, max_lines: int | None = None) -> list[CodeChunk]:
    """
    Split ``content`` into embeddable chunks.

    Strategy:
      1. Try the tree-sitter symbol extractor (top-level functions/classes).
      2. Fill any gaps (imports, module-level statements) with window chunks.
      3. If there is no grammar or parsing fails, use pure window chunking.
    """
    if not content or not content.strip():
        return []

    max_lines = max_lines or settings.CHUNK_MAX_LINES
    language = detect_language(file_path) or "Text"
    lines = content.splitlines()
    total_lines = len(lines)

    parser = _load_parser(language)

    if parser is not None:
        try:
            source = content.encode("utf-8", errors="replace")
            tree = parser.parse(source)
            symbol_chunks: list[CodeChunk] = []
            covered: list[tuple[int, int]] = []  # 0-based line ranges already emitted

            for node in _top_level_symbol_nodes(tree.root_node, language):
                start = node.start_point[0]
                end = node.end_point[0]
                text = _node_text(source, node).rstrip()
                if not text.strip():
                    continue
                # Oversized symbols are split further so embeddings stay focused.
                if end - start + 1 > max_lines * 2:
                    symbol_chunks.extend(
                        _window_chunks(
                            file_path,
                            language,
                            lines[start : end + 1],
                            line_offset=start,
                            max_lines=max_lines,
                        )
                    )
                else:
                    symbol_chunks.append(
                        CodeChunk(
                            file_path=file_path,
                            language=language,
                            content=text,
                            start_line=start + 1,
                            end_line=end + 1,
                            symbol=_node_name(node),
                            kind=_KIND_BY_NODE.get(node.type, "block"),
                        )
                    )
                covered.append((start, end))

            # Emit the uncovered regions (imports, globals, trailing code).
            gap_chunks = _gap_chunks(file_path, language, lines, covered, max_lines=max_lines)
            chunks = _sorted_chunks(symbol_chunks) + [c for c in gap_chunks]
            chunks = [c for c in chunks if len(c.content.strip()) > 0]
            if chunks:
                return _dedupe_and_trim(chunks, max_lines=max_lines)
        except Exception as exc:  # pragma: no cover
            logger.debug("Tree-sitter parsing failed for %s: %s", file_path, exc)

    return _window_chunks(file_path, language, lines, line_offset=0, max_lines=max_lines)


def _sorted_chunks(chunks: list[CodeChunk]) -> list[CodeChunk]:
    return sorted(chunks, key=lambda c: c.start_line)


def _top_level_symbol_nodes(root: Any, language: str) -> list[Any]:
    """
    Collect the outermost symbol nodes.

    We deliberately **do not descend** into a symbol once matched, so a class
    becomes a single chunk rather than one chunk per method.
    """
    targets = _SYMBOL_NODES.get(language, set())
    if not targets:
        return []

    found: list[Any] = []

    def visit(node: Any) -> None:
        for child in node.children:
            if child.type in targets:
                found.append(child)
                continue  # do not descend into the symbol
            if child.child_count:
                visit(child)

    visit(root)
    return found


def _window_chunks(
    file_path: str,
    language: str,
    lines: list[str],
    *,
    line_offset: int,
    max_lines: int,
) -> list[CodeChunk]:
    """
    Sliding-window fallback chunker.

    Windows prefer to break on blank lines so a window rarely ends mid-statement.
    """
    chunks: list[CodeChunk] = []
    min_lines = max(1, settings.CHUNK_MIN_LINES)
    index = 0
    total = len(lines)

    while index < total:
        end = min(index + max_lines, total)

        # Look backwards for a blank line to cut on (never below min_lines).
        if end < total:
            for probe in range(end, min(end - 20, index + min_lines) - 1, -1):
                if probe > index and not lines[probe - 1].strip():
                    end = probe
                    break

        block = "\n".join(lines[index:end]).rstrip()
        if block.strip():
            chunks.append(
                CodeChunk(
                    file_path=file_path,
                    language=language,
                    content=block,
                    start_line=line_offset + index + 1,
                    end_line=line_offset + end,
                    symbol=None,
                    kind="window",
                )
            )

        if end <= index:  # safety net against infinite loops
            end = index + 1
        index = end

    return chunks


def _gap_chunks(
    file_path: str,
    language: str,
    lines: list[str],
    covered: list[tuple[int, int]],
    *,
    max_lines: int,
) -> list[CodeChunk]:
    """Chunk the lines not covered by any symbol (0-based ranges)."""
    if not covered:
        return _window_chunks(file_path, language, lines, line_offset=0, max_lines=max_lines)

    merged = _merge_ranges(covered)
    gaps: list[tuple[int, int]] = []
    cursor = 0
    for start, end in merged:
        if start > cursor:
            gaps.append((cursor, start - 1))
        cursor = max(cursor, end + 1)
    if cursor < len(lines):
        gaps.append((cursor, len(lines) - 1))

    chunks: list[CodeChunk] = []
    for start, end in gaps:
        segment = lines[start : end + 1]
        if not "".join(segment).strip():
            continue  # skip pure whitespace / trailing blanks
        chunks.extend(
            _window_chunks(file_path, language, segment, line_offset=start, max_lines=max_lines)
        )
    return chunks


def _merge_ranges(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    ordered = sorted(ranges)
    merged: list[tuple[int, int]] = []
    for start, end in ordered:
        if merged and start <= merged[-1][1] + 1:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _dedupe_and_trim(chunks: list[CodeChunk], *, max_lines: int) -> list[CodeChunk]:
    """Drop chunks that are too small to be useful, keeping order."""
    min_lines = settings.CHUNK_MIN_LINES
    result: list[CodeChunk] = []
    for chunk in chunks:
        span = chunk.end_line - chunk.start_line + 1
        if span < min_lines and not chunk.symbol:
            continue
        result.append(chunk)
    return result


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 chars/token) used to budget prompts."""
    return max(1, len(text) // 4)


__all__ = ["CodeChunk", "chunk_file", "estimate_tokens"]
