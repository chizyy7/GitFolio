import { CalendarDays, Flame, GitCommitHorizontal, Trophy } from "lucide-react";

import type { StreakStats } from "@/lib/types";
import { cn, formatNumber } from "@/lib/utils";

interface Props {
  stats: StreakStats;
  className?: string;
}

interface StatCardProps {
  icon: React.ReactNode;
  label: string;
  value: string;
  hint?: string;
  accent?: string;
}

function StatCard({ icon, label, value, hint, accent }: StatCardProps) {
  return (
    <div className="card flex items-center gap-3 p-3.5">
      <span
        className={cn(
          "grid h-9 w-9 shrink-0 place-items-center rounded-md border",
          accent ?? "border-border bg-canvas text-fg-muted",
        )}
      >
        {icon}
      </span>
      <div className="min-w-0">
        <p className="truncate text-2xs uppercase tracking-wide text-fg-muted">{label}</p>
        <p className="text-lg font-semibold leading-tight">{value}</p>
        {hint && <p className="truncate text-2xs text-fg-subtle">{hint}</p>}
      </div>
    </div>
  );
}

/**
 * Headline statistics: total commits, streaks and churn.
 */
export function StatsRow({ stats, className }: Props) {
  return (
    <div className={cn("grid grid-cols-2 gap-3 lg:grid-cols-4", className)}>
      <StatCard
        icon={<GitCommitHorizontal className="h-4 w-4" />}
        label="Total commits"
        value={formatNumber(stats.total_commits)}
        hint={`${formatNumber(stats.active_days)} active days`}
        accent="border-accent/30 bg-accent/10 text-accent"
      />
      <StatCard
        icon={<Flame className="h-4 w-4" />}
        label="Current streak"
        value={`${stats.current_streak}d`}
        hint={stats.current_streak > 0 ? "Keep it going!" : "Push something today"}
        accent="border-attention/30 bg-attention/10 text-attention"
      />
      <StatCard
        icon={<Trophy className="h-4 w-4" />}
        label="Longest streak"
        value={`${stats.longest_streak}d`}
        hint="Personal record"
        accent="border-done/30 bg-done/10 text-done"
      />
      <StatCard
        icon={<CalendarDays className="h-4 w-4" />}
        label="Lines changed"
        value={formatNumber(stats.total_additions + stats.total_deletions)}
        hint={`+${formatNumber(stats.total_additions)} / -${formatNumber(stats.total_deletions)}`}
        accent="border-success/30 bg-success/10 text-success"
      />
    </div>
  );
}
