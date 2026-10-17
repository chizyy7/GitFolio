"use client";

import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { ActivityPoint } from "@/lib/types";
import { formatDate } from "@/lib/utils";

interface Props {
  activity: ActivityPoint[];
}

/**
 * Weekly commit activity (Recharts area chart).
 *
 * Complements the heatmap: the heatmap answers "did I code that day?", this
 * chart answers "is my output trending up or down?".
 */
export function ActivityChart({ activity }: Props) {
  const data = activity.map((point) => ({
    ...point,
    label: formatDate(point.week_start).replace(/\s\d{4}$/, ""),
  }));

  const hasData = activity.some((point) => point.commits > 0);

  if (!hasData) {
    return (
      <section className="card p-4">
        <h2 className="text-sm font-semibold">Commit activity</h2>
        <p className="mt-6 mb-6 text-center text-sm text-fg-muted">
          No commits in this period yet. Push some code to see your trend.
        </p>
      </section>
    );
  }

  return (
    <section className="card p-4">
      <header className="mb-4">
        <h2 className="text-sm font-semibold">Commit activity</h2>
        <p className="text-xs text-fg-muted">Commits per week over the last {activity.length} weeks</p>
      </header>

      <div className="h-52 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 4, right: 8, left: -22, bottom: 0 }}>
            <defs>
              <linearGradient id="commitFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="rgb(88 166 255)" stopOpacity={0.45} />
                <stop offset="100%" stopColor="rgb(88 166 255)" stopOpacity={0.02} />
              </linearGradient>
            </defs>

            <CartesianGrid stroke="rgb(48 54 61)" strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="label"
              tick={{ fill: "rgb(139 148 158)", fontSize: 10 }}
              tickLine={false}
              axisLine={{ stroke: "rgb(48 54 61)" }}
              interval="preserveStartEnd"
              minTickGap={28}
            />
            <YAxis
              tick={{ fill: "rgb(139 148 158)", fontSize: 10 }}
              tickLine={false}
              axisLine={false}
              allowDecimals={false}
              width={40}
            />
            <Tooltip
              cursor={{ stroke: "rgb(88 166 255)", strokeDasharray: "3 3" }}
              contentStyle={{
                background: "rgb(22 27 34)",
                border: "1px solid rgb(48 54 61)",
                borderRadius: 8,
                fontSize: 12,
              }}
              labelStyle={{ color: "rgb(230 237 243)", fontWeight: 600 }}
              itemStyle={{ color: "rgb(139 148 158)" }}
              formatter={(value: number, name: string) => {
                if (name === "commits") return [value, "Commits"];
                if (name === "additions") return [value, "Lines added"];
                if (name === "deletions") return [value, "Lines removed"];
                return [value, name];
              }}
              labelFormatter={(_label, payload) => {
                const point = payload?.[0]?.payload as ActivityPoint | undefined;
                return point ? `Week of ${formatDate(point.week_start)}` : "";
              }}
            />
            <Area
              type="monotone"
              dataKey="commits"
              stroke="rgb(88 166 255)"
              strokeWidth={2}
              fill="url(#commitFill)"
              animationDuration={600}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
