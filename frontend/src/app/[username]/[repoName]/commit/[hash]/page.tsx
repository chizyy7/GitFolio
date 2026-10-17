"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  Check,
  Copy,
  GitCommitHorizontal,
  Sparkles,
} from "lucide-react";

import { CommitDiff } from "@/components/CommitDiff";
import { ReviewComments } from "@/components/ReviewComments";
import { ErrorPanel, PageLoader } from "@/components/RequireAuth";
import { ApiError, reposApi, vcsApi } from "@/lib/api";
import type { CommitDetail } from "@/lib/types";
import { formatDateTime, formatRelative } from "@/lib/utils";

/**
 * Single-commit page: metadata, the unified diff and the AI code review.
 *
 * Because the version-control API is keyed by repository id, we first resolve
 * `username/repo` to its id, then load the commit by (possibly short) hash.
 */
export default function CommitPage() {
  const params = useParams<{ username: string; repoName: string; hash: string }>();
  const username = decodeURIComponent(params.username ?? "");
  const repoName = decodeURIComponent(params.repoName ?? "");
  const hash = decodeURIComponent(params.hash ?? "");

  const [commit, setCommit] = useState<CommitDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<{ status: number; message: string } | null>(null);
  const [copied, setCopied] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const repo = await reposApi.detail(username, repoName);
      setCommit(await vcsApi.commit(repo.id, hash));
    } catch (err) {
      if (err instanceof ApiError) setError({ status: err.status, message: err.detail });
      else setError({ status: 0, message: "Could not load this commit." });
    } finally {
      setLoading(false);
    }
  }, [username, repoName, hash]);

  useEffect(() => {
    load();
  }, [load]);

  const copyHash = useCallback(async () => {
    if (!commit) return;
    await navigator.clipboard.writeText(commit.commit_hash);
    setCopied(true);
    setTimeout(() => setCopied(false), 1600);
  }, [commit]);

  if (loading && !commit) return <PageLoader label="Loading commit…" />;
  if (error) {
    return (
      <ErrorPanel
        title={error.status === 404 ? "Commit not found" : "Commit unavailable"}
        message={
          error.status === 404
            ? `No commit “${hash.slice(0, 12)}” exists in ${username}/${repoName}.`
            : error.message
        }
        onRetry={error.status === 404 ? undefined : load}
      />
    );
  }
  if (!commit) return null;

  return (
    <div className="space-y-5">
      <Link
        href={`/${username}/${repoName}`}
        className="inline-flex items-center gap-1.5 text-xs text-fg-muted hover:text-fg"
      >
        <ArrowLeft className="h-3.5 w-3.5" /> Back to {username}/{repoName}
      </Link>

      {/* Commit header */}
      <header className="card p-5">
        <h1 className="whitespace-pre-wrap text-base font-semibold leading-snug">
          {commit.message}
        </h1>

        <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-fg-muted">
          {commit.author?.avatar_url ? (
            <img
              src={commit.author.avatar_url}
              alt=""
              width={20}
              height={20}
              className="h-5 w-5 rounded-full border border-border"
            />
          ) : (
            <span className="grid h-5 w-5 place-items-center rounded-full bg-canvas-subtle text-2xs">
              {commit.author?.username.slice(0, 2) ?? "??"}
            </span>
          )}
          <span className="font-medium text-fg">@{commit.author?.username ?? "unknown"}</span>
          <span title={formatDateTime(commit.timestamp)}>{formatRelative(commit.timestamp)}</span>

          <span className="inline-flex items-center gap-1.5">
            <GitCommitHorizontal className="h-3.5 w-3.5" />
            <code className="font-mono">{commit.short_hash}</code>
            <button
              type="button"
              onClick={copyHash}
              className="btn btn-ghost h-5 !px-1 text-fg-muted"
              title="Copy full commit hash"
            >
              {copied ? <Check className="h-3 w-3 text-success" /> : <Copy className="h-3 w-3" />}
            </button>
          </span>

          <span className="font-mono">
            <span className="text-success">+{commit.additions}</span>{" "}
            <span className="text-danger">-{commit.deletions}</span>
          </span>

          <span>
            {commit.files_changed} file{commit.files_changed === 1 ? "" : "s"} changed
          </span>

          {commit.ai_reviewed && (
            <span className="badge border-accent/40 bg-accent/10 text-accent">
              <Sparkles className="h-2.5 w-2.5" /> reviewed
            </span>
          )}
        </div>

        {commit.parent_hash && (
          <p className="mt-3 text-2xs text-fg-subtle">
            Parent{" "}
            <code className="font-mono">{commit.parent_hash.slice(0, 12)}</code>
          </p>
        )}
      </header>

      {/* AI review */}
      <ReviewComments commitId={commit.id} ownerUsername={username} />

      {/* Diff */}
      <section className="space-y-3">
        <h2 className="text-sm font-semibold">Changes</h2>
        <CommitDiff diff={commit.diff} />
      </section>
    </div>
  );
}
