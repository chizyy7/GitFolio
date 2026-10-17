/**
 * Small formatting / styling helpers shared across the UI.
 */

import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/** Tailwind-aware className combiner. */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

/** `2026-03-04T12:31:00Z` -> `4 Mar 2026`. */
export function formatDate(value: string | Date | null | undefined): string {
  if (!value) return "—";
  const date = typeof value === "string" ? new Date(value) : value;
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

/** `4 Mar 2026 at 12:31`. */
export function formatDateTime(value: string | Date | null | undefined): string {
  if (!value) return "—";
  const date = typeof value === "string" ? new Date(value) : value;
  if (Number.isNaN(date.getTime())) return "—";
  return `${formatDate(date)} at ${date.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
  })}`;
}

/** "3 days ago" style relative time. */
export function formatRelative(value: string | Date | null | undefined): string {
  if (!value) return "—";
  const date = typeof value === "string" ? new Date(value) : value;
  const seconds = Math.round((Date.now() - date.getTime()) / 1000);

  const table: [Intl.RelativeTimeFormatUnit, number][] = [
    ["year", 60 * 60 * 24 * 365],
    ["month", 60 * 60 * 24 * 30],
    ["week", 60 * 60 * 24 * 7],
    ["day", 60 * 60 * 24],
    ["hour", 60 * 60],
    ["minute", 60],
    ["second", 1],
  ];

  const formatter = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
  for (const [unit, secondsInUnit] of table) {
    if (Math.abs(seconds) >= secondsInUnit || unit === "second") {
      return formatter.format(-Math.round(seconds / secondsInUnit), unit);
    }
  }
  return "just now";
}

/** 1234 -> "1,234"; 12345 -> "12.3k". */
export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return "0";
  if (Math.abs(value) >= 1000) {
    return `${(value / 1000).toFixed(value % 1000 === 0 ? 0 : 1)}k`;
  }
  return value.toLocaleString();
}

/** Byte size for file trees. */
export function formatBytes(bytes: number | null | undefined): string {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const exponent = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const value = bytes / Math.pow(1024, exponent);
  return `${value.toFixed(exponent === 0 ? 0 : 1)} ${units[exponent]}`;
}

/** Turn a repo/file path into a readable breadcrumb list. */
export function breadcrumbParts(path: string): string[] {
  return path.split("/").filter(Boolean);
}

// --------------------------------------------------------------------------- //
// Colour maps
// --------------------------------------------------------------------------- //
export const LANGUAGE_COLORS: Record<string, string> = {
  Python: "#3572A5",
  TypeScript: "#3178c6",
  JavaScript: "#f1e05a",
  TSX: "#3178c6",
  JSX: "#f1e05a",
  HTML: "#e34c26",
  CSS: "#563d7c",
  SCSS: "#c6538c",
  Vue: "#41b883",
  Svelte: "#ff3e00",
  C: "#555555",
  "C++": "#f34b7d",
  "C#": "#178600",
  Java: "#b07219",
  Kotlin: "#A97BFF",
  Go: "#00ADD8",
  Rust: "#dea584",
  Swift: "#F05138",
  PHP: "#4F5D95",
  Ruby: "#701516",
  Scala: "#c22d40",
  Dart: "#00B4AB",
  Lua: "#000080",
  R: "#198CE7",
  Julia: "#a270ba",
  SQL: "#e38c00",
  Shell: "#89e051",
  PowerShell: "#012456",
  Dockerfile: "#384d54",
  Makefile: "#427819",
  Markdown: "#083fa1",
  JSON: "#292929",
  YAML: "#cb171e",
  TOML: "#9c4221",
  "Jupyter Notebook": "#DA5B0B",
  Text: "#8b949e",
};

/** Deterministic colour for a language (falls back to a neutral grey). */
export function languageColor(language: string | null | undefined): string {
  if (!language) return "#8b949e";
  return LANGUAGE_COLORS[language] ?? "#8b949e";
}

export const SEVERITY_STYLES: Record<
  string,
  { label: string; className: string; dot: string }
> = {
  Bug: {
    label: "Bug",
    className: "border-danger/40 bg-danger/10 text-danger",
    dot: "#f85149",
  },
  Security: {
    label: "Security",
    className: "border-done/40 bg-done/10 text-done",
    dot: "#a371f7",
  },
  Style: {
    label: "Style",
    className: "border-attention/40 bg-attention/10 text-attention",
    dot: "#d29922",
  },
  Suggestion: {
    label: "Suggestion",
    className: "border-accent/40 bg-accent/10 text-accent",
    dot: "#58a6ff",
  },
};

export const PROFICIENCY_STYLES: Record<string, string> = {
  Advanced: "border-success/40 bg-success/10 text-success",
  Intermediate: "border-accent/40 bg-accent/10 text-accent",
  Beginner: "border-border bg-canvas-subtle text-fg-muted",
};

/** Map a Shiki language id onto one of the grammars we ship. */
export function toShikiLang(language: string | null | undefined): string {
  if (!language) return "text";
  const map: Record<string, string> = {
    Python: "python",
    TypeScript: "typescript",
    TSX: "tsx",
    JavaScript: "javascript",
    JSX: "jsx",
    JSON: "json",
    YAML: "yaml",
    TOML: "toml",
    HTML: "html",
    CSS: "css",
    SCSS: "scss",
    Markdown: "markdown",
    SQL: "sql",
    Shell: "bash",
    "C++": "cpp",
    "C#": "csharp",
    Go: "go",
    Rust: "rust",
    Java: "java",
    PHP: "php",
    Ruby: "ruby",
    Dockerfile: "docker",
    INI: "ini",
    XML: "xml",
    Text: "text",
  };
  return map[language] ?? "text";
}

/** Truncate long strings with an ellipsis. */
export function truncate(value: string, max = 120): string {
  return value.length <= max ? value : `${value.slice(0, max - 1)}…`;
}

/** Initials for avatar fallbacks. */
export function initials(value: string | null | undefined): string {
  if (!value) return "??";
  return value
    .split(/[\s-_]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}
