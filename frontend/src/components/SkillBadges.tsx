"use client";

import { useState } from "react";
import { RefreshCw, Sparkles } from "lucide-react";

import { aiApi } from "@/lib/api";
import type { SkillRead } from "@/lib/types";
import { PROFICIENCY_STYLES, cn } from "@/lib/utils";

interface Props {
  skills: SkillRead[];
  /** Show the "regenerate" button (only for the signed-in owner). */
  canRefresh?: boolean;
  onRefresh?: (skills: SkillRead[]) => void;
}

const CATEGORY_ORDER = ["language", "framework", "tool", "database", "other"];

/**
 * AI-generated skill badges, grouped by category.
 *
 * The badges come from the AI skill mapper (`POST /api/ai/skills/refresh`),
 * which analyses file extensions and dependency manifests across every
 * repository the user owns.
 */
export function SkillBadges({ skills, canRefresh = false, onRefresh }: Props) {
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const grouped = CATEGORY_ORDER.map((category) => ({
    category,
    items: skills.filter((skill) => skill.category === category),
  })).filter((group) => group.items.length > 0);

  const refresh = async () => {
    setRefreshing(true);
    setError(null);
    try {
      const profile = await aiApi.refreshSkills(true);
      // The endpoint returns the profile; reload the badge list from the source
      // of truth so category/confidence match what was persisted.
      const summary = [
        ...profile.languages.map((name) => ({ name, category: "language", proficiency: profile.proficiency })),
        ...profile.frameworks.map((name) => ({ name, category: "framework", proficiency: profile.proficiency })),
        ...profile.tools.map((name) => ({ name, category: "tool", proficiency: profile.proficiency })),
        ...profile.databases.map((name) => ({ name, category: "database", proficiency: profile.proficiency })),
      ];
      onRefresh?.(
        summary.map((item, index) => ({
          id: `local-${index}`,
          skill_name: item.name,
          proficiency: item.proficiency,
          category: item.category,
          confidence: 0,
          evidence: profile.summary,
        })),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not refresh skills.");
    } finally {
      setRefreshing(false);
    }
  };

  if (skills.length === 0) {
    return (
      <section className="card p-4">
        <header className="mb-2 flex items-center justify-between">
          <h2 className="flex items-center gap-1.5 text-sm font-semibold">
            <Sparkles className="h-3.5 w-3.5 text-done" /> AI Skills
          </h2>
          {canRefresh && (
            <button type="button" onClick={refresh} disabled={refreshing} className="btn h-6 text-2xs">
              <RefreshCw className={cn("h-3 w-3", refreshing && "animate-spin")} /> Analyse
            </button>
          )}
        </header>
        <p className="text-xs text-fg-muted">
          No skills detected yet. Push a repository and GitFolio will profile your stack
          automatically.
        </p>
        {error && <p className="mt-2 text-2xs text-danger">{error}</p>}
      </section>
    );
  }

  return (
    <section className="card p-4">
      <header className="mb-3 flex items-center justify-between">
        <h2 className="flex items-center gap-1.5 text-sm font-semibold">
          <Sparkles className="h-3.5 w-3.5 text-done" /> AI Skills
        </h2>
        {canRefresh && (
          <button
            type="button"
            onClick={refresh}
            disabled={refreshing}
            className="btn h-6 text-2xs"
            title="Re-run the AI skill mapper"
          >
            <RefreshCw className={cn("h-3 w-3", refreshing && "animate-spin")} /> Re-analyse
          </button>
        )}
      </header>

      <div className="space-y-3">
        {grouped.map((group) => (
          <div key={group.category}>
            <p className="mb-1.5 text-2xs uppercase tracking-wide text-fg-subtle">{group.category}</p>
            <div className="flex flex-wrap gap-1.5">
              {group.items.map((skill) => (
                <span
                  key={skill.id}
                  className={cn(
                    "badge",
                    PROFICIENCY_STYLES[skill.proficiency] ?? PROFICIENCY_STYLES.Beginner,
                  )}
                  title={
                    skill.evidence ??
                    `${skill.skill_name} — ${skill.proficiency}${
                      skill.confidence ? ` (confidence ${skill.confidence}%)` : ""
                    }`
                  }
                >
                  {skill.skill_name}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>

      {error && <p className="mt-3 text-2xs text-danger">{error}</p>}
    </section>
  );
}
