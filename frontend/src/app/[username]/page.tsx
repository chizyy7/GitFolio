"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { BookMarked, LayoutGrid, Search } from "lucide-react";

import { ContributionHeatmap } from "@/components/ContributionHeatmap";
import { PinnedRepos } from "@/components/PinnedRepos";
import { ProfileSidebar } from "@/components/ProfileSidebar";
import { RepoCard } from "@/components/RepoCard";
import { ErrorPanel, PageLoader } from "@/components/RequireAuth";
import { ApiError, dashboardApi, reposApi, usersApi } from "@/lib/api";
import type { HeatmapResponse, RepoRead, UserProfile } from "@/lib/types";
import { cn, formatNumber } from "@/lib/utils";

type Tab = "overview" | "repositories";

/**
 * Public developer profile.
 *
 * Fetches the profile card, the repository list and the contribution heatmap on
 * the client so the signed-in owner also sees their private repositories. The
 * `?tab=` query parameter lets the sidebar's "Repositories" stat deep-link here.
 */
export default function ProfilePage() {
  return (
    <Suspense fallback={<PageLoader />}>
      <ProfileView />
    </Suspense>
  );
}

function ProfileView() {
  const params = useParams<{ username: string }>();
  const username = decodeURIComponent(params.username ?? "");
  const searchParams = useSearchParams();

  const requestedTab = searchParams.get("tab");
  const [tab, setTab] = useState<Tab>(requestedTab === "repositories" ? "repositories" : "overview");

  // Keep the active tab in sync with `?tab=` — client-side <Link> navigation to
  // the same route does not remount this component.
  useEffect(() => {
    setTab(requestedTab === "repositories" ? "repositories" : "overview");
  }, [requestedTab]);

  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [repos, setRepos] = useState<RepoRead[]>([]);
  const [heatmap, setHeatmap] = useState<HeatmapResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<{ status: number; message: string } | null>(null);
  const [query, setQuery] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [profileData, repoList] = await Promise.all([
        usersApi.profile(username),
        reposApi.list(username, { sort: "updated", per_page: 100 }),
      ]);
      setProfile(profileData);
      setRepos(repoList);

      // The heatmap is best-effort — a failure should not blank the profile.
      try {
        setHeatmap(await dashboardApi.heatmap(username));
      } catch {
        setHeatmap(null);
      }
    } catch (err) {
      if (err instanceof ApiError) {
        setError({ status: err.status, message: err.detail });
      } else {
        setError({ status: 0, message: "Could not load this profile." });
      }
    } finally {
      setLoading(false);
    }
  }, [username]);

  useEffect(() => {
    load();
  }, [load]);

  const filteredRepos = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return repos;
    return repos.filter(
      (repo) =>
        repo.name.toLowerCase().includes(needle) ||
        (repo.description ?? "").toLowerCase().includes(needle) ||
        (repo.primary_language ?? "").toLowerCase().includes(needle),
    );
  }, [repos, query]);

  if (loading && !profile) return <PageLoader label={`Loading @${username}…`} />;

  if (error) {
    return (
      <ErrorPanel
        title={error.status === 404 ? "Profile not found" : "Profile unavailable"}
        message={
          error.status === 404
            ? `No GitFolio account named “${username}”.`
            : error.message
        }
        onRetry={error.status === 404 ? undefined : load}
      />
    );
  }

  if (!profile) return null;

  return (
    <div className="grid gap-6 lg:grid-cols-[300px_1fr]">
      <ProfileSidebar profile={profile} />

      <div className="min-w-0 space-y-5">
        {/* Tabs */}
        <nav className="flex gap-1 border-b border-border" role="tablist">
          <TabButton
            active={tab === "overview"}
            onClick={() => setTab("overview")}
            icon={<LayoutGrid className="h-3.5 w-3.5" />}
            label="Overview"
          />
          <TabButton
            active={tab === "repositories"}
            onClick={() => setTab("repositories")}
            icon={<BookMarked className="h-3.5 w-3.5" />}
            label="Repositories"
            count={repos.length}
          />
        </nav>

        {tab === "overview" ? (
          <div className="space-y-5">
            <PinnedRepos repos={repos.slice(0, 6)} username={username} title="Pinned" />

            {heatmap ? (
              <ContributionHeatmap
                days={heatmap.days}
                totalLabel={`${formatNumber(
                  heatmap.days.reduce((sum, day) => sum + day.count, 0),
                )} contributions in the last year`}
              />
            ) : (
              <section className="card p-4">
                <h2 className="text-sm font-semibold">Contribution activity</h2>
                <p className="mt-4 text-xs text-fg-muted">
                  No contribution data available for @{username}.
                </p>
              </section>
            )}
          </div>
        ) : (
          <div className="space-y-4">
            <div className="relative">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-fg-subtle" />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Find a repository…"
                className="input pl-8"
                aria-label={`Search @${username}'s repositories`}
              />
            </div>

            {filteredRepos.length === 0 ? (
              <div className="card p-10 text-center text-sm text-fg-muted">
                {repos.length === 0
                  ? `@${username} has no repositories yet.`
                  : "No repositories match your search."}
              </div>
            ) : (
              <div className="grid gap-3 sm:grid-cols-2">
                {filteredRepos.map((repo) => (
                  <RepoCard key={repo.id} repo={repo} />
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  icon,
  label,
  count,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
  count?: number;
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={onClick}
      className={cn(
        "-mb-px inline-flex items-center gap-1.5 border-b-2 px-3 py-2 text-xs font-medium transition",
        active
          ? "border-attention text-fg"
          : "border-transparent text-fg-muted hover:border-border hover:text-fg",
      )}
    >
      {icon}
      {label}
      {count !== undefined && (
        <span className="rounded-full bg-canvas-subtle px-1.5 text-2xs text-fg-muted">{count}</span>
      )}
    </button>
  );
}
