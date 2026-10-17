"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { CheckCircle2, FilePlus2, GitCommitHorizontal, Sparkles, Trash2, Upload, Wand2 } from "lucide-react";

import { ApiError, reposApi, vcsApi } from "@/lib/api";
import type { PushResponse } from "@/lib/types";
import { cn } from "@/lib/utils";

interface Props {
  repoId: string;
  repoName: string;
  /** Owner of the repository — needed to fetch a file's current content. */
  username: string;
  /** Current file paths (used to prefill edits). */
  existingPaths?: string[];
  onPushed?: (response: PushResponse) => void;
}

interface DraftFile {
  id: string;
  path: string;
  content: string;
  deleting?: boolean;
}

const SAMPLE_FILES: { path: string; content: string }[] = [
  {
    path: "README.md",
    content: `# ${"My Project"}

A short description of what this does.

## Getting started

\`\`\`bash
npm install
npm run dev
\`\`\`
`,
  },
  {
    path: "src/auth.py",
    content: `"""Authentication helpers."""
import hashlib
import hmac

SECRET = "super-secret-key-please-change"


def hash_password(password: str) -> str:
    """Hash a password with SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str, hashed: str) -> bool:
    """Constant-time password verification."""
    return hmac.compare_digest(hash_password(password), hashed)


def authenticate(username: str, password: str) -> bool:
    """Look the user up and verify their password."""
    record = db.users.find_one({"username": username})
    if record is None:
        return False
    return verify_password(password, record["password_hash"])
`,
  },
  {
    path: "src/db.py",
    content: `"""Database connection helpers."""
import os


def get_connection():
    """Open a connection using the DATABASE_URL environment variable."""
    dsn = os.environ.get("DATABASE_URL", "sqlite:///./app.db")
    return connect(dsn)
`,
  },
];

/**
 * Web-based push panel.
 *
 * This is the same operation as the CLI/`git push` equivalent:
 * `POST /api/repos/{repo_id}/push`. Use it to seed a repository from the
 * browser, then watch the AI pipeline kick in (review + embeddings).
 */
export function PushPanel({ repoId, repoName, username, existingPaths = [], onPushed }: Props) {
  const router = useRouter();
  const [files, setFiles] = useState<DraftFile[]>([]);
  const [commitMessage, setCommitMessage] = useState("");
  const [runAi, setRunAi] = useState(true);
  const [pushing, setPushing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PushResponse | null>(null);
  const [loadingPath, setLoadingPath] = useState<string | null>(null);

  const addFile = (path = "", content = "") => {
    setFiles((current) => [
      ...current,
      { id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`, path, content },
    ]);
  };

  /**
   * Load an existing file's current content before editing it.
   *
   * Seeding the editor with an empty string would make the next push truncate
   * the file, so we fetch the real content first.
   */
  const editExisting = async (path: string) => {
    setError(null);
    setLoadingPath(path);
    try {
      const file = await reposApi.file(username, repoName, path);
      addFile(path, file.content);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? `Could not load ${path}: ${err.detail}`
          : `Could not load ${path}.`,
      );
    } finally {
      setLoadingPath(null);
    }
  };

  const updateFile = (id: string, patch: Partial<DraftFile>) => {
    setFiles((current) => current.map((file) => (file.id === id ? { ...file, ...patch } : file)));
  };

  const removeFile = (id: string) => {
    setFiles((current) => current.filter((file) => file.id !== id));
  };

  const push = async () => {
    setError(null);
    setResult(null);

    const payload = files.filter((file) => file.path.trim());
    if (payload.length === 0) {
      setError("Add at least one file before pushing.");
      return;
    }

    setPushing(true);
    try {
      const response = await vcsApi.push(repoId, {
        files: payload.map(({ path, content }) => ({ path: path.trim(), content })),
        commit_message: commitMessage.trim() || null,
        run_ai: runAi,
      });
      setResult(response);
      setFiles([]);
      setCommitMessage("");
      router.refresh();
      onPushed?.(response);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Push failed.");
    } finally {
      setPushing(false);
    }
  };

  return (
    <section className="card p-4" aria-label="Push files">
      <header className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="flex items-center gap-1.5 text-sm font-semibold">
            <Upload className="h-3.5 w-3.5" /> Push files to {repoName}
          </h2>
          <p className="text-xs text-fg-muted">
            Creates a real Git commit (SHA-1 via pygit2), stores the diff and queues the AI review.
          </p>
        </div>

        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => SAMPLE_FILES.forEach((file) => addFile(file.path, file.content))}
            className="btn h-7 text-2xs"
          >
            <Sparkles className="h-3 w-3" /> Add sample files
          </button>
          <button type="button" onClick={() => addFile()} className="btn h-7 text-2xs">
            <FilePlus2 className="h-3 w-3" /> Add file
          </button>
        </div>
      </header>

      {existingPaths.length > 0 && files.length === 0 && (
        <div className="mb-3 flex flex-wrap gap-1.5">
          <span className="text-2xs text-fg-muted">Edit an existing file:</span>
          {existingPaths.slice(0, 8).map((path) => (
            <button
              key={path}
              type="button"
              disabled={loadingPath !== null}
              onClick={() => editExisting(path)}
              className="chip hover:bg-accent/20 disabled:opacity-50"
            >
              {loadingPath === path ? "Loading…" : path}
            </button>
          ))}
        </div>
      )}

      <div className="space-y-3">
        {files.map((file) => (
          <div key={file.id} className="rounded-md border border-border bg-canvas p-3">
            <div className="mb-2 flex items-center gap-2">
              <input
                value={file.path}
                onChange={(event) => updateFile(file.id, { path: event.target.value })}
                placeholder="src/components/Button.tsx"
                className="input h-8 flex-1 text-xs"
                aria-label="File path"
              />
              <button
                type="button"
                onClick={() => removeFile(file.id)}
                className="btn btn-ghost h-8 !px-2 text-danger"
                aria-label={`Remove ${file.path || "file"}`}
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
            <textarea
              value={file.content}
              onChange={(event) => updateFile(file.id, { content: event.target.value })}
              rows={8}
              spellCheck={false}
              placeholder="// file contents"
              className="input resize-y font-mono text-xs leading-5"
              aria-label="File contents"
            />
          </div>
        ))}
      </div>

      <div className="mt-4 space-y-3">
        <label className="block">
          <span className="mb-1 flex items-center gap-1.5 text-xs font-medium text-fg-muted">
            <GitCommitHorizontal className="h-3.5 w-3.5" /> Commit message
          </span>
          <input
            value={commitMessage}
            onChange={(event) => setCommitMessage(event.target.value)}
            placeholder="Leave blank to let Llama 3.2 write it from the diff"
            className="input"
          />
          {!commitMessage.trim() && (
            <span className="mt-1 flex items-center gap-1 text-2xs text-done">
              <Wand2 className="h-3 w-3" /> Auto-Commit Message Generator will run
            </span>
          )}
        </label>

        <label className="flex items-center gap-2 text-xs text-fg-muted">
          <input
            type="checkbox"
            checked={runAi}
            onChange={(event) => setRunAi(event.target.checked)}
            className="h-3.5 w-3.5 rounded border-border bg-canvas-inset"
          />
          Run the AI pipeline (embed for search + code review)
        </label>

        {error && <p className="text-xs text-danger">{error}</p>}

        {result && (
          <div className="rounded-md border border-success/40 bg-success/10 p-3 text-xs">
            <p className="flex items-center gap-1.5 font-semibold text-success">
              <CheckCircle2 className="h-3.5 w-3.5" /> Commit {result.short_hash} created
            </p>
            <p className="mt-1 whitespace-pre-wrap text-fg-muted">{result.message}</p>
            <p className="mt-1.5 font-mono text-2xs text-fg-subtle">
              {result.files_changed} file{result.files_changed === 1 ? "" : "s"} ·{" "}
              <span className="text-success">+{result.additions}</span>{" "}
              <span className="text-danger">-{result.deletions}</span>
              {result.message_generated && " · message generated by AI"}
              {result.ai_queued && " · AI review queued"}
            </p>
            <ul className="mt-2 space-y-0.5">
              {result.files.map((file) => (
                <li key={file.path} className="font-mono text-2xs text-fg-muted">
                  <span
                    className={cn(
                      "mr-1.5",
                      file.change_type === "Added" && "text-success",
                      file.change_type === "Modified" && "text-attention",
                      file.change_type === "Deleted" && "text-danger",
                    )}
                  >
                    {file.change_type[0]}
                  </span>
                  {file.path}
                </li>
              ))}
            </ul>
          </div>
        )}

        <button
          type="button"
          onClick={push}
          disabled={pushing || files.length === 0}
          className="btn btn-primary w-full text-xs"
        >
          {pushing ? "Committing…" : `Push ${files.length || ""} file${files.length === 1 ? "" : "s"}`}
        </button>
      </div>
    </section>
  );
}
