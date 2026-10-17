"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, SearchX } from "lucide-react";

import { RepoWorkspace } from "@/components/RepoWorkspace";
import { ErrorPanel, PageLoader } from "@/components/RequireAuth";
import { ApiError, reposApi, vcsApi } from "@/lib/api";
import type { CommitRead, RepoDetail } from "@/lib/types";

/**
 * Repository page: header, file tree, commit history, AI assistant and push.
 *
 * Data is fetched on the client so the owner's private repositories resolve
 * with their bearer token; ownership for the Push tab is derived from the auth
 * context inside `RepoWorkspace`.
 */
export default function RepositoryPage() {
  const params = useParams<{ username: string; repoName: string }>();
  const username = decodeURIComponent(params.username ?? "");
  const repoName = decodeURIComponent(params.repoName ?? "");

  const [repo, setRepo] = useState<RepoDetail | null>(null);
  const [commits, setCommits] = useState<CommitRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<{ status: number; message: string } | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const detail = await reposApi.detail(username, repoName);
      setRepo(detail);

      // Commit history is secondary; a failure leaves the Code tab usable.
      try {
        const history = await vcsApi.commits(detail.id, { per_page: 50 });
        setCommits(history.items);
      } catch {
        setCommits([]);
      }
    } catch (err) {
      if (err instanceof ApiError) setError({ status: err.status, message: err.detail });
      else setError({ status: 0, message: "Could not load this repository." });
    } finally {
      setLoading(false);
    }
  }, [username, repoName]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading && !repo) return <PageLoader label={`Opening ${username}/${repoName}…`} />;

  if (error) {
    if (error.status === 404) {
      return (
        <div className="card mx-auto max-w-lg p-8 text-center">
          <span className="mx-auto mb-3 grid h-11 w-11 place-items-center rounded-full border border-border bg-canvas text-fg-muted">
            <SearchX className="h-5 w-5" />
          </span>
          <h1 className="text-sm font-semibold">Repository not found</h1>
          <p className="mt-2 text-xs text-fg-muted">
            <code className="font-mono">
              {username}/{repoName}
            </code>{" "}
            does not exist, or it is private and you are not the owner.
          </p>
          <Link href={`/${username}`} className="btn mx-auto mt-5 text-xs">
            <ArrowLeft className="h-3.5 w-3.5" /> Back to @{username}
          </Link>
        </div>
      );
    }
    return <ErrorPanel title="Repository unavailable" message={error.message} onRetry={load} />;
  }

  if (!repo) return null;

  return <RepoWorkspace repo={repo} commits={commits} username={username} onRefresh={load} />;
}
