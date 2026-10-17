"use client";

import { useMemo, useState } from "react";
import CalendarHeatmap from "react-calendar-heatmap";
import "react-calendar-heatmap/dist/styles.css";

import type { HeatmapDay } from "@/lib/types";
import { cn, formatDate } from "@/lib/utils";

interface Props {
  days: HeatmapDay[];
  /** Rendered above the grid — usually "N contributions in the last year". */
  totalLabel?: string;
  onSelectDay?: (day: HeatmapDay) => void;
  initialWeeks?: number;
}

interface HoverState {
  day: HeatmapDay | null;
  x: number;
  y: number;
}

const WEEK_OPTIONS = [
  { label: "3 months", weeks: 13 },
  { label: "6 months", weeks: 26 },
  { label: "1 year", weeks: 53 },
];

/**
 * GitHub-style contribution heatmap.
 *
 * `react-calendar-heatmap` renders the SVG grid; we supply the class names,
 * the dark-mode colour ramp (via CSS variables) and a fully custom hover
 * tooltip so the experience matches GitHub rather than the library's default
 * native browser tooltip.
 */
export function ContributionHeatmap({ days, totalLabel, onSelectDay, initialWeeks = 53 }: Props) {
  const [weeks, setWeeks] = useState(initialWeeks);
  const [hover, setHover] = useState<HoverState>({ day: null, x: 0, y: 0 });

  const visibleDays = useMemo(() => days.slice(Math.max(0, days.length - weeks * 7)), [days, weeks]);

  const values = useMemo(
    () =>
      visibleDays.map((day) => ({
        date: day.date,
        count: day.count,
        level: day.level,
        additions: day.additions,
        deletions: day.deletions,
      })),
    [visibleDays],
  );

  const total = useMemo(
    () => visibleDays.reduce((sum, day) => sum + day.count, 0),
    [visibleDays],
  );

  const startDate = visibleDays.at(0)?.date ?? new Date();
  const endDate = visibleDays.at(-1)?.date ?? new Date();

  return (
    <section className="card p-4 sm:p-5" aria-label="Contribution activity">
      <header className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold">{totalLabel ?? `${total} contributions`}</h2>
          <p className="text-xs text-fg-muted">
            Commit activity over the last {WEEK_OPTIONS.find((option) => option.weeks === weeks)?.label ?? "year"}
          </p>
        </div>

        <div className="flex items-center gap-1 rounded-md border border-border p-0.5">
          {WEEK_OPTIONS.map((option) => (
            <button
              key={option.weeks}
              type="button"
              onClick={() => setWeeks(option.weeks)}
              className={cn(
                "rounded px-2 py-1 text-2xs transition",
                weeks === option.weeks
                  ? "bg-accent-emphasis text-fg-onEmphasis"
                  : "text-fg-muted hover:bg-canvas-subtle hover:text-fg",
              )}
            >
              {option.label}
            </button>
          ))}
        </div>
      </header>

      <div className="relative overflow-x-auto pb-1">
        <CalendarHeatmap
          startDate={startDate}
          endDate={endDate}
          values={values}
          showMonthLabels
          showWeekdayLabels
          gutterSize={3}
          classForValue={(value) => {
            if (!value) return "level-0";
            const level = (value as { level?: number }).level ?? 0;
            return `level-${level}`;
          }}
          onClick={(value) => {
            const day = value as (HeatmapDay & { date: string }) | undefined;
            if (day) onSelectDay?.({ ...day, level: (day.level ?? 0) as HeatmapDay["level"] });
          }}
          onMouseOver={(event, value) => {
            const day = value as (HeatmapDay & { date: string }) | undefined;
            if (!day) return;

            const rect = (event.target as SVGRectElement).getBoundingClientRect();
            const container = event.currentTarget
              .closest("div")
              ?.getBoundingClientRect();

            setHover({
              day: {
                date: day.date,
                count: day.count ?? 0,
                level: (day.level ?? 0) as HeatmapDay["level"],
                additions: day.additions ?? 0,
                deletions: day.deletions ?? 0,
              },
              x: rect.left - (container?.left ?? 0) + rect.width / 2,
              y: rect.top - (container?.top ?? 0) - 8,
            });
          }}
          onMouseLeave={() => setHover({ day: null, x: 0, y: 0 })}
        />

        {/* Custom tooltip */}
        {hover.day && (
          <div
            role="tooltip"
            style={{ left: hover.x, top: hover.y }}
            className="pointer-events-none absolute z-20 -translate-x-1/2 -translate-y-full whitespace-nowrap rounded-md border border-border bg-canvas-overlay px-2.5 py-1.5 text-2xs shadow-popover"
          >
            <p className="font-semibold">
              {hover.day.count === 0
                ? "No contributions"
                : `${hover.day.count} contribution${hover.day.count === 1 ? "" : "s"}`}
            </p>
            <p className="text-fg-muted">{formatDate(hover.day.date)}</p>
            {(hover.day.additions > 0 || hover.day.deletions > 0) && (
              <p className="mt-0.5 font-mono">
                <span className="text-success">+{hover.day.additions}</span>{" "}
                <span className="text-danger">-{hover.day.deletions}</span>
              </p>
            )}
          </div>
        )}
      </div>

      {/* Legend */}
      <footer className="mt-3 flex items-center justify-between gap-3 text-2xs text-fg-muted">
        <span className="hidden sm:inline">Hover a square for details</span>
        <div className="ml-auto flex items-center gap-1.5">
          <span>Less</span>
          {[0, 1, 2, 3, 4].map((level) => (
            <span
              key={level}
              aria-hidden
              style={{ background: `rgb(var(--heat-${level}))` }}
              className="h-2.5 w-2.5 rounded-sm border border-canvas"
            />
          ))}
          <span>More</span>
        </div>
      </footer>
    </section>
  );
}
