import Link from "next/link";
import { GitCommitHorizontal, Sparkles, Wand2 } from "lucide-react";

import type { CommitRead } from "@/lib/types";
import { cn, formatNumber, formatRelative } from "@/lib/utils";

interface Props {
  commits: CommitRead[];
  username: string;
  repoName: string;
  /** Show the short hash column (hidden in tight layouts). */
  compact?: boolean;
  className?: string;
}

/**
 * Commit history list — one row per commit, GitHub style.
 *
 * Shows the AI-review badge when the commit has been reviewed, and marks
 * messages that were written by the Auto-Commit Message Generator.
 */
export function CommitList({ commits, username, repoName, compact = false, className }: Props) {
  if (commits.length === 0) {
    return (
      <div className="card flex flex-col items-center gap-2 p-10 text-center">
        <GitCommitHorizontal className="h-6 w-6 text-fg-subtle" />
        <p className="text-sm text-fg-muted">No commits yet.</p>
        <p className="text-xs text-fg-subtle">Push your first commit to start the history.</p>
      </div>
    );
  }

  return (
    <div className={cn("card divide-y divide-border overflow-hidden", className)}>
      {commits.map((commit) => (
        <article key={commit.id} className="flex items-start gap-3 p-3.5 transition hover:bg-canvas">
          {commit.author?.avatar_url ? (
            <img
              src={commit.author.avatar_url}
              alt=""
              width={28}
              height={28}
              className="mt-0.5 h-7 w-7 shrink-0 rounded-full border border-border"
            />
          ) : (
            <span className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-full bg-canvas-subtle text-2xs text-fg-muted">
              {commit.author?.username.slice(0, 2) ?? "??"}
            </span>
          )}

          <div className="min-w-0 flex-1">
            <Link
              href={`/${username}/${repoName}/commit/${commit.commit_hash}`}
              className="line-clamp-1 text-sm font-medium hover:text-accent hover:underline"
              title={commit.message}
            >
              {commit.summary}
            </Link>

            <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-2xs text-fg-muted">
              <span className="font-medium text-fg-muted">@{commit.author?.username ?? "unknown"}</span>
              <span aria-hidden>·</span>
              <span title={commit.timestamp}>{formatRelative(commit.timestamp)}</span>
              {!compact && (
                <>
                  <span aria-hidden>·</span>
                  <code className="font-mono">{commit.short_hash}</code>
                </>
              )}
              <span className="inline-flex items-center gap-1.5">
                <span className="text-success">+{formatNumber(commit.additions)}</span>
                <span className="text-danger">-{formatNumber(commit.deletions)}</span>
              </span>

              {commit.message_generated && (
                <span className="badge border-done/40 bg-done/10 text-done" title="Message written by the AI">
                  <Wand2 className="h-2.5 w-2.5" /> auto
                </span>
              )}
              {commit.ai_reviewed && (
                <span className="badge border-accent/40 bg-accent/10 text-accent" title="AI review available">
                  <Sparkles className="h-2.5 w-2.5" /> reviewed
                </span>
              )}
            </p>
          </div>

          <Link
            href={`/${username}/${repoName}/commit/${commit.commit_hash}`}
            className="btn btn-ghost hidden h-6 shrink-0 text-2xs sm:inline-flex"
          >
            Browse
          </Link>
        </article>
      ))}
    </div>
  );
}
