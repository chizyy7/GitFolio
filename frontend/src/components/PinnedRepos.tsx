"use client";

import Link from "next/link";
import { FolderGit2 } from "lucide-react";

import { RepoCard } from "@/components/RepoCard";
import { CreateRepoButton } from "@/components/CreateRepoButton";
import { useAuth } from "@/context/AuthContext";
import type { RepoRead } from "@/lib/types";

interface Props {
  repos: RepoRead[];
  username: string;
  title?: string;
}

/**
 * Pinned repositories grid (falls back to the most active repos, which is what
 * the backend returns when nothing is explicitly pinned).
 *
 * Ownership is derived from the auth context so the viewer sees the "New"
 * button only on their own profile.
 */
export function PinnedRepos({ repos, username, title = "Pinned" }: Props) {
  const { user } = useAuth();
  const isOwner = user?.username === username;

  return (
    <section>
      <header className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold">{title}</h2>
        {isOwner && <CreateRepoButton />}
      </header>

      {repos.length === 0 ? (
        <div className="card flex flex-col items-center justify-center gap-2 p-10 text-center">
          <FolderGit2 className="h-6 w-6 text-fg-subtle" />
          <p className="text-sm text-fg-muted">
            {isOwner
              ? "You have no repositories yet. Create one and push your first commit."
              : `@${username} has no public repositories yet.`}
          </p>
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {repos.map((repo) => (
            <RepoCard key={repo.id} repo={repo} />
          ))}
        </div>
      )}

      {repos.length > 0 && (
        <div className="mt-3">
          <Link
            href={`/${username}?tab=repositories`}
            className="text-xs text-accent hover:underline"
          >
            View all repositories →
          </Link>
        </div>
      )}
    </section>
  );
}
