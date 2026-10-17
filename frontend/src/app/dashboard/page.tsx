"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { LayoutDashboard, Plus, RefreshCw } from "lucide-react";

import { ActivityChart } from "@/components/ActivityChart";
import { ContributionHeatmap } from "@/components/ContributionHeatmap";
import { CreateRepoButton } from "@/components/CreateRepoButton";
import { LanguageChart } from "@/components/LanguageChart";
import { PinnedRepos } from "@/components/PinnedRepos";
import { ErrorPanel, PageLoader, RequireAuth } from "@/components/RequireAuth";
import { StatsRow } from "@/components/StatsRow";
import { ApiError, dashboardApi } from "@/lib/api";
import type { DashboardResponse, UserMe } from "@/lib/types";
import { formatNumber } from "@/lib/utils";

/**
 * Personal dashboard.
 *
 * One request (`GET /api/dashboard/{username}`) returns the contribution
 * heatmap, weekly activity, language split and pinned repositories.
 */
export default function DashboardPage() {
  return (
    <RequireAuth message="Sign in to see your contribution history and repositories.">
      {(user) => <Dashboard user={user} />}
    </RequireAuth>
  );
}

function Dashboard({ user }: { user: UserMe }) {
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await dashboardApi.get(user.username));
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not load your dashboard.");
    } finally {
      setLoading(false);
    }
  }, [user.username]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-lg font-semibold">
            <LayoutDashboard className="h-5 w-5 text-fg-muted" />
            Welcome back, {user.display_name ?? user.username}
          </h1>
          <p className="mt-0.5 text-xs text-fg-muted">
            Your contribution history, language mix and pinned repositories.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button type="button" onClick={load} disabled={loading} className="btn h-8 text-xs">
            <RefreshCw className={loading ? "h-3.5 w-3.5 animate-spin" : "h-3.5 w-3.5"} /> Refresh
          </button>
          <CreateRepoButton />
          <Link href={`/${user.username}`} className="btn h-8 text-xs">
            View profile
          </Link>
        </div>
      </header>

      {loading && !data ? (
        <PageLoader label="Building your dashboard…" />
      ) : error ? (
        <ErrorPanel title="Dashboard unavailable" message={error} onRetry={load} />
      ) : data ? (
        <>
          <StatsRow stats={data.heatmap.stats} />

          <ContributionHeatmap
            days={data.heatmap.days}
            totalLabel={`${formatNumber(
              data.heatmap.days.reduce((sum, day) => sum + day.count, 0),
            )} contributions in the last year`}
          />

          <div className="grid gap-4 lg:grid-cols-2">
            <ActivityChart activity={data.activity} />
            <LanguageChart languages={data.languages} />
          </div>

          <section>
            <header className="mb-3 flex items-center justify-between">
              <h2 className="text-sm font-semibold">Pinned repositories</h2>
              <Link href={`/${user.username}?tab=repositories`} className="text-xs text-accent hover:underline">
                All repositories →
              </Link>
            </header>

            {data.pinned_repos.length === 0 ? (
              <div className="card flex flex-col items-center gap-3 p-10 text-center">
                <Plus className="h-6 w-6 text-fg-subtle" />
                <p className="text-sm font-medium">No repositories yet</p>
                <p className="max-w-sm text-xs text-fg-muted">
                  Create your first repository, then push a folder of code from your machine or
                  seed files directly in the browser.
                </p>
                <CreateRepoButton />
              </div>
            ) : (
              <PinnedRepos repos={data.pinned_repos} username={user.username} title="Pinned" />
            )}
          </section>
        </>
      ) : null}
    </div>
  );
}
