"use client";

import { useState } from "react";
import { FileCode2, Search, Sparkles } from "lucide-react";

import { ApiError, aiApi } from "@/lib/api";
import type { SearchResponse } from "@/lib/types";
import { cn } from "@/lib/utils";

interface Props {
  repoId: string;
  onOpenFile?: (path: string, line?: number) => void;
}

const EXAMPLES = [
  "where is the database connection created",
  "function that hashes a password",
  "request validation and error responses",
  "how commits are created and stored",
];

/**
 * Semantic code search.
 *
 * Unlike a text search, this embeds the query and matches on *meaning*, so
 * "function that hashes a password" finds `hash_password` even though the
 * words never appear together.
 */
export function CodeSearch({ repoId, onOpenFile }: Props) {
  const [query, setQuery] = useState("");
  const [response, setResponse] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const search = async (value: string) => {
    const trimmed = value.trim();
    if (!trimmed) return;

    setLoading(true);
    setError(null);
    try {
      const result = await aiApi.search({ repo_id: repoId, query: trimmed, top_k: 8, summarise: true });
      setResponse(result);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Search failed.");
      setResponse(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="card p-4" aria-label="Semantic code search">
      <header className="mb-3">
        <h2 className="flex items-center gap-1.5 text-sm font-semibold">
          <Sparkles className="h-3.5 w-3.5 text-done" /> Semantic code search
        </h2>
        <p className="text-xs text-fg-muted">
          Search by intent, not by substring. Powered by embeddings over AST-level code chunks.
        </p>
      </header>

      <form
        onSubmit={(event) => {
          event.preventDefault();
          search(query);
        }}
        className="flex gap-2"
      >
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-fg-subtle" />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="e.g. how are JWTs verified?"
            className="input pl-8"
            aria-label="Search query"
          />
        </div>
        <button type="submit" disabled={loading || !query.trim()} className="btn btn-primary text-xs">
          {loading ? "Searching…" : "Search"}
        </button>
      </form>

      {!response && !loading && !error && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {EXAMPLES.map((example) => (
            <button
              key={example}
              type="button"
              onClick={() => {
                setQuery(example);
                search(example);
              }}
              className="chip hover:bg-accent/20"
            >
              {example}
            </button>
          ))}
        </div>
      )}

      {error && <p className="mt-3 text-xs text-danger">{error}</p>}

      {response && (
        <div className="mt-4 space-y-2">
          {response.results.length === 0 ? (
            <p className="text-xs text-fg-muted">
              No matches. The repository may not be indexed yet — build the index from the AI tab.
            </p>
          ) : (
            <>
              {response.results[0]?.summary && (
                <p className="rounded-md border border-accent/30 bg-accent/10 p-3 text-xs leading-relaxed">
                  <strong className="font-semibold">Summary: </strong>
                  {response.results[0].summary}
                </p>
              )}

              {response.results.map((hit, index) => (
                <button
                  key={`${hit.file_path}-${hit.start_line}-${index}`}
                  type="button"
                  onClick={() => onOpenFile?.(hit.file_path, hit.start_line)}
                  className="w-full rounded-md border border-border bg-canvas p-3 text-left transition hover:border-accent/50"
                >
                  <header className="mb-1.5 flex items-center gap-2">
                    <FileCode2 className="h-3.5 w-3.5 shrink-0 text-fg-subtle" />
                    <span className="truncate font-mono text-xs text-accent">
                      {hit.file_path}:{hit.start_line}-{hit.end_line}
                    </span>
                    {hit.symbol && (
                      <span className="chip shrink-0">{hit.symbol}</span>
                    )}
                    <span className="ml-auto shrink-0 font-mono text-2xs text-fg-subtle">
                      {(hit.score * 100).toFixed(0)}%
                    </span>
                  </header>

                  {/* Relevance bar */}
                  <div className="mb-2 h-1 w-full overflow-hidden rounded-full bg-canvas-subtle">
                    <div
                      className={cn("h-full rounded-full bg-accent")}
                      style={{ width: `${Math.max(4, Math.min(100, hit.score * 100))}%` }}
                    />
                  </div>

                  <pre className="max-h-32 overflow-hidden text-2xs leading-5 text-fg-muted">
                    <code>{hit.snippet.slice(0, 420)}</code>
                  </pre>
                </button>
              ))}

              <p className="text-2xs text-fg-subtle">
                {response.results.length} results in {(response.elapsed_ms / 1000).toFixed(2)}s
              </p>
            </>
          )}
        </div>
      )}
    </section>
  );
}
