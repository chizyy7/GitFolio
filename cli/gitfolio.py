#!/usr/bin/env python3
"""
GitFolio command-line client.

A dependency-free helper (standard library only) for talking to a GitFolio
instance from a terminal — the same operations the web UI performs.

Examples
--------
Sign in and capture a token::

    python cli/gitfolio.py login --api http://localhost:8000/api \\
        --username octocat --password secret

Push a local directory as a single commit::

    python cli/gitfolio.py push ./my-project \\
        --api http://localhost:8000/api \\
        --token "$GITFOLIO_TOKEN" \\
        --repo 2f1c... \\
        --message "feat: initial import"

Preview what would be sent without contacting the server::

    python cli/gitfolio.py push ./my-project --repo 2f1c... --dry-run

Environment variables (used as defaults):
    GITFOLIO_API    base API URL, e.g. http://localhost:8000/api
    GITFOLIO_TOKEN  bearer token
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_API = os.environ.get("GITFOLIO_API", "http://localhost:8000/api")

# Mirrors the backend's default ignore list; keeps the payload small and skips
# anything that would be treated as binary anyway.
DEFAULT_IGNORED = [
    ".git", "node_modules", "dist", "build", ".next", "__pycache__",
    ".venv", "venv", ".mypy_cache", ".pytest_cache", "coverage",
    ".idea", ".vscode", ".DS_Store",
]

BINARY_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".webp", ".bmp", ".tiff",
    ".pdf", ".zip", ".tar", ".gz", ".bz2", ".7z", ".rar",
    ".woff", ".woff2", ".ttf", ".otf", ".eot",
    ".mp3", ".mp4", ".mov", ".avi", ".mkv", ".webm",
    ".so", ".dll", ".dylib", ".exe", ".bin", ".class", ".jar", ".pyc",
    ".sqlite", ".db", ".lock",
}


# --------------------------------------------------------------------------- #
# HTTP helpers (stdlib only — no `requests`/`httpx` required)
# --------------------------------------------------------------------------- #
def _request(
    method: str,
    url: str,
    *,
    token: str | None = None,
    payload: dict | None = None,
    timeout: float = 300.0,
) -> dict:
    """Perform a JSON request and return the decoded response body."""
    data = json.dumps(payload).encode("utf-8") if payload is not None else None

    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(detail)
            detail = parsed.get("detail", detail)
        except json.JSONDecodeError:
            pass
        raise SystemExit(f"error: HTTP {exc.code} — {detail}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(
            f"error: could not reach {url}\n       {exc.reason}\n"
            f"       Is the GitFolio API running and is --api correct?"
        ) from exc


# --------------------------------------------------------------------------- #
# Filesystem helpers
# --------------------------------------------------------------------------- #
def _is_binary(path: Path) -> bool:
    """Best-effort binary detection: by extension, then by a NUL-byte probe."""
    if path.suffix.lower() in BINARY_SUFFIXES:
        return True
    try:
        with path.open("rb") as handle:
            return b"\x00" in handle.read(4096)
    except OSError:
        return True


def collect_files(
    root: Path,
    *,
    ignored: list[str],
    max_bytes: int,
) -> tuple[list[dict], list[str]]:
    """
    Walk ``root`` and return ``(files, skipped)``.

    ``files`` is a list of ``{"path", "content"}`` payloads with POSIX-style,
    root-relative paths (exactly what the push endpoint expects).
    """
    files: list[dict] = []
    skipped: list[str] = []

    ignored_set = set(ignored)

    for current_dir, dir_names, file_names in os.walk(root):
        # Prune ignored directories in place so os.walk never descends into them.
        dir_names[:] = [name for name in dir_names if name not in ignored_set]

        for file_name in file_names:
            absolute = Path(current_dir) / file_name
            relative = absolute.relative_to(root).as_posix()

            if any(part in ignored_set for part in relative.split("/")):
                skipped.append(relative)
                continue
            if _is_binary(absolute):
                skipped.append(f"{relative} (binary)")
                continue

            try:
                size = absolute.stat().st_size
            except OSError:
                skipped.append(relative)
                continue

            if size > max_bytes:
                skipped.append(f"{relative} ({size // 1024} KB > limit)")
                continue

            try:
                content = absolute.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                skipped.append(f"{relative} (unreadable)")
                continue

            files.append({"path": relative, "content": content})

    files.sort(key=lambda item: item["path"])
    return files, skipped


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #
def cmd_login(args: argparse.Namespace) -> None:
    """Authenticate and print a token suitable for GITFOLIO_TOKEN."""
    result = _request(
        "POST",
        f"{args.api.rstrip('/')}/auth/login",
        payload={"username": args.username, "password": args.password},
    )
    token = result.get("access_token", "")
    user = result.get("user", {})
    print(f"Signed in as @{user.get('username', args.username)}")
    print("\nAdd this to your shell (do not commit it):\n")
    print(f"export GITFOLIO_TOKEN={token}")


def cmd_whoami(args: argparse.Namespace) -> None:
    """Print the account behind the configured token."""
    token = args.token or os.environ.get("GITFOLIO_TOKEN")
    if not token:
        raise SystemExit("error: no token. Pass --token or set GITFOLIO_TOKEN.")
    user = _request("GET", f"{args.api.rstrip('/')}/auth/me", token=token)
    print(json.dumps(user, indent=2))


def cmd_push(args: argparse.Namespace) -> None:
    """Push a local directory to a GitFolio repository."""
    token = args.token or os.environ.get("GITFOLIO_TOKEN")
    root = Path(args.path).resolve()

    if not root.is_dir():
        raise SystemExit(f"error: '{root}' is not a directory.")
    if not args.repo:
        raise SystemExit("error: --repo is required (the repository id from GitFolio).")

    ignored = list(dict.fromkeys(DEFAULT_IGNORED + list(args.ignore or [])))
    files, skipped = collect_files(root, ignored=ignored, max_bytes=args.max_bytes)

    if not files and not args.delete:
        raise SystemExit("error: no pushable files found (everything was ignored or binary).")

    payload = {
        "files": files,
        "deleted_paths": list(args.delete or []),
        "commit_message": args.message,
        "branch": args.branch,
        "run_ai": not args.no_ai,
    }

    total_bytes = sum(len(item["content"].encode("utf-8")) for item in files)
    print(f"Repository : {args.repo}")
    print(f"Source     : {root}")
    print(f"Files      : {len(files)} ({total_bytes // 1024} KB)")
    if args.delete:
        print(f"Deleting   : {', '.join(args.delete)}")
    if skipped:
        print(f"Skipped    : {len(skipped)} entr{'y' if len(skipped) == 1 else 'ies'}")
        for entry in skipped[:10]:
            print(f"             - {entry}")
        if len(skipped) > 10:
            print(f"             … and {len(skipped) - 10} more")

    if args.dry_run:
        print("\n[dry-run] Nothing was sent. Remove --dry-run to push.")
        return

    if not token:
        raise SystemExit("\nerror: no token. Pass --token or set GITFOLIO_TOKEN.")

    endpoint = f"{args.api.rstrip('/')}/repos/{args.repo}/push"
    print("\nPushing…")
    result = _request("POST", endpoint, token=token, payload=payload)

    print(f"\n✓ Commit {result.get('short_hash')} created")
    print(f"  {result.get('message')}")
    print(
        f"  {result.get('files_changed')} file(s) · "
        f"+{result.get('additions')} / -{result.get('deletions')}"
    )
    if result.get("message_generated"):
        print("  (message written by the AI)")
    if result.get("ai_queued"):
        print("  AI review + embedding queued in the background")


# --------------------------------------------------------------------------- #
# Argument parsing
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gitfolio",
        description="GitFolio command-line client — push code and talk to the AI-powered API.",
    )
    parser.add_argument("--api", default=DEFAULT_API, help=f"API base URL (default: {DEFAULT_API})")
    parser.add_argument("--token", default=None, help="Bearer token (default: $GITFOLIO_TOKEN)")

    sub = parser.add_subparsers(dest="command", required=True)

    login = sub.add_parser("login", help="Authenticate and print an access token")
    login.add_argument("--username", required=True)
    login.add_argument("--password", required=True)
    login.set_defaults(func=cmd_login)

    whoami = sub.add_parser("whoami", help="Show the account for the current token")
    whoami.set_defaults(func=cmd_whoami)

    push = sub.add_parser("push", help="Push a local directory as a commit")
    push.add_argument("path", nargs="?", default=".", help="Directory to push (default: .)")
    push.add_argument("--repo", required=True, help="Target repository id")
    push.add_argument("--message", default=None, help="Commit message (omit to let the AI write it)")
    push.add_argument("--branch", default=None, help="Target branch (default: the repo's default)")
    push.add_argument(
        "--delete",
        action="append",
        default=[],
        metavar="PATH",
        help="Repository path to delete (repeatable)",
    )
    push.add_argument(
        "--ignore",
        action="append",
        default=[],
        metavar="NAME",
        help="Extra directory/file name to ignore (repeatable)",
    )
    push.add_argument("--max-bytes", type=int, default=512 * 1024, help="Per-file size limit")
    push.add_argument("--no-ai", action="store_true", help="Skip the AI review/embedding pipeline")
    push.add_argument("--dry-run", action="store_true", help="Show what would be pushed, send nothing")
    push.set_defaults(func=cmd_push)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
