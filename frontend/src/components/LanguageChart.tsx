"use client";

import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

import type { LanguageStat } from "@/lib/types";
import { languageColor } from "@/lib/utils";

interface Props {
  languages: LanguageStat[];
}

/**
 * Language distribution across a user's repositories (Recharts doughnut).
 */
export function LanguageChart({ languages }: Props) {
  if (languages.length === 0) {
    return (
      <section className="card p-4">
        <h2 className="text-sm font-semibold">Languages</h2>
        <p className="mt-6 mb-6 text-center text-sm text-fg-muted">
          No language data yet — push some code.
        </p>
      </section>
    );
  }

  const data = languages.slice(0, 7).map((stat) => ({
    name: stat.language,
    value: stat.repo_count,
    percentage: stat.percentage,
  }));

  return (
    <section className="card p-4">
      <header className="mb-2">
        <h2 className="text-sm font-semibold">Most used languages</h2>
        <p className="text-xs text-fg-muted">Across {languages.length} language{languages.length === 1 ? "" : "s"}</p>
      </header>

      <div className="h-52 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              dataKey="value"
              nameKey="name"
              innerRadius="52%"
              outerRadius="78%"
              paddingAngle={2}
              stroke="rgb(13 17 23)"
              strokeWidth={2}
            >
              {data.map((entry) => (
                <Cell key={entry.name} fill={languageColor(entry.name)} />
              ))}
            </Pie>
            <Tooltip
              contentStyle={{
                background: "rgb(22 27 34)",
                border: "1px solid rgb(48 54 61)",
                borderRadius: 8,
                fontSize: 12,
              }}
              formatter={(value: number, name: string) => [`${value} repo${value === 1 ? "" : "s"}`, name]}
            />
            <Legend
              verticalAlign="bottom"
              height={36}
              iconType="circle"
              iconSize={8}
              formatter={(value: string) => (
                <span style={{ color: "rgb(139 148 158)", fontSize: 11 }}>{value}</span>
              )}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
