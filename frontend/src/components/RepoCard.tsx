import Link from "next/link";
import { GitCommitHorizontal, Lock, Star } from "lucide-react";

import type { RepoRead } from "@/lib/types";
import { cn, formatNumber, formatRelative, languageColor } from "@/lib/utils";

interface Props {
  repo: RepoRead;
  className?: string;
}

/**
 * Repository card used on profiles, the dashboard and the explore page.
 *
 * Mirrors GitHub's pinned-repo card: name, visibility, description, language
 * dot with byte share, star count and last-updated time.
 */
export function RepoCard({ repo, className }: Props) {
  return (
    <article
      className={cn(
        "card flex h-full flex-col justify-between p-4 transition hover:border-fg-subtle",
        className,
      )}
    >
      <div>
        <header className="flex items-start justify-between gap-2">
          <div className="flex min-w-0 items-center gap-1.5">
            <Link
              href={`/${repo.owner_username}/${repo.name}`}
              className="truncate text-sm font-semibold text-accent hover:underline"
              title={repo.name}
            >
              {repo.name}
            </Link>
            <span
              className="badge shrink-0 border-border bg-canvas text-fg-muted"
              title={repo.visibility}
            >
              {repo.visibility === "Private" ? (
                <>
                  <Lock className="h-2.5 w-2.5" /> Private
                </>
              ) : (
                "Public"
              )}
            </span>
          </div>

          {repo.is_pinned && (
            <span className="badge shrink-0 border-attention/40 bg-attention/10 text-attention" title="Pinned">
              Pinned
            </span>
          )}
        </header>

        <p className="mt-2 line-clamp-2 min-h-[2.5rem] text-xs leading-relaxed text-fg-muted">
          {repo.description ?? "No description provided."}
        </p>

        {repo.topics.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {repo.topics.slice(0, 4).map((topic) => (
              <span key={topic} className="chip">
                {topic}
              </span>
            ))}
          </div>
        )}
      </div>

      <footer className="mt-4 flex flex-wrap items-center gap-3 text-2xs text-fg-muted">
        {repo.primary_language && (
          <span className="inline-flex items-center gap-1.5">
            <span
              aria-hidden
              className="h-2.5 w-2.5 rounded-full"
              style={{ backgroundColor: languageColor(repo.primary_language) }}
            />
            {repo.primary_language}
          </span>
        )}
        <span className="inline-flex items-center gap-1">
          <Star className="h-3 w-3" /> {formatNumber(repo.star_count)}
        </span>
        <span className="inline-flex items-center gap-1" title={`${repo.commit_count} commits`}>
          <GitCommitHorizontal className="h-3 w-3" /> {formatNumber(repo.commit_count)}
        </span>
        <span className="ml-auto">Updated {formatRelative(repo.updated_at)}</span>
      </footer>
    </article>
  );
}
