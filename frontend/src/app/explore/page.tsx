"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Compass, Search, Users } from "lucide-react";

import { Avatar } from "@/components/Navbar";
import { ErrorPanel, PageLoader } from "@/components/RequireAuth";
import { ApiError, usersApi } from "@/lib/api";
import type { UserRead } from "@/lib/types";
import { formatDate } from "@/lib/utils";

/**
 * Developer directory.
 *
 * Lists GitFolio accounts (newest first) with a debounced search across
 * usernames and display names — the entry point for discovering portfolios.
 */
export default function ExplorePage() {
  const [users, setUsers] = useState<UserRead[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (term: string) => {
    setLoading(true);
    setError(null);
    try {
      setUsers(await usersApi.list({ q: term || undefined, per_page: 48 }));
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not load the developer directory.");
    } finally {
      setLoading(false);
    }
  }, []);

  // Debounced search — the initial (empty) term loads everyone.
  useEffect(() => {
    const timer = setTimeout(() => load(query.trim()), query ? 350 : 0);
    return () => clearTimeout(timer);
  }, [query, load]);

  return (
    <div className="space-y-6">
      <header className="space-y-3">
        <div>
          <h1 className="flex items-center gap-2 text-lg font-semibold">
            <Compass className="h-5 w-5 text-fg-muted" /> Explore developers
          </h1>
          <p className="mt-0.5 text-xs text-fg-muted">
            Discover portfolios built with GitFolio — repositories, AI reviews and skill profiles.
          </p>
        </div>

        <div className="relative max-w-md">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-fg-subtle" />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search by username or name…"
            className="input pl-8"
            aria-label="Search developers"
          />
        </div>
      </header>

      {loading && users.length === 0 ? (
        <PageLoader label="Loading developers…" />
      ) : error ? (
        <ErrorPanel message={error} onRetry={() => load(query.trim())} />
      ) : users.length === 0 ? (
        <div className="card flex flex-col items-center gap-2 p-12 text-center">
          <Users className="h-6 w-6 text-fg-subtle" />
          <p className="text-sm font-medium">No developers found</p>
          <p className="text-xs text-fg-muted">
            {query ? `Nothing matches “${query}”.` : "Be the first to create an account."}
          </p>
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {users.map((user) => (
            <Link
              key={user.id}
              href={`/${user.username}`}
              className="card flex items-start gap-3 p-4 transition hover:border-fg-subtle"
            >
              <Avatar user={user} size={44} />
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold">{user.display_name ?? user.username}</p>
                <p className="truncate text-xs text-fg-muted">@{user.username}</p>
                {user.bio ? (
                  <p className="mt-1.5 line-clamp-2 text-2xs leading-relaxed text-fg-muted">
                    {user.bio}
                  </p>
                ) : (
                  <p className="mt-1.5 text-2xs text-fg-subtle">Joined {formatDate(user.created_at)}</p>
                )}
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
