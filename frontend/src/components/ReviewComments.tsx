"use client";

import { useEffect, useState } from "react";
import { AlertCircle, CheckCircle2, RefreshCw, ShieldAlert, Sparkles } from "lucide-react";

import { ApiError, aiApi } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import type { ReviewResponse } from "@/lib/types";
import { SEVERITY_STYLES, cn } from "@/lib/utils";

interface Props {
  commitId: string;
  initial?: ReviewResponse;
  /** Owner of the repository the commit belongs to. */
  ownerUsername: string;
}

const POLL_MS = 3000;
const MAX_POLLS = 40;

/**
 * AI code-review panel for a commit.
 *
 * The review is produced in the background after a push, so this component
 * polls while the status is `pending` and stops as soon as it is resolved.
 * The "Re-run" control is shown only to the signed-in owner.
 */
export function ReviewComments({ commitId, initial, ownerUsername }: Props) {
  const { user } = useAuth();
  const canRerun = user?.username === ownerUsername;

  const [data, setData] = useState<ReviewResponse | null>(initial ?? null);
  const [loading, setLoading] = useState(!initial);
  const [error, setError] = useState<string | null>(null);
  const [polls, setPolls] = useState(0);
  // Bumped to restart polling after a manual "Re-run".
  const [pollToken, setPollToken] = useState(0);

  // --------------------------------------------------------------- polling
  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    // Local attempt counter: reading `polls` state inside `load` would close
    // over a stale value and poll forever.
    let attempts = 0;

    async function load() {
      try {
        const result = await aiApi.reviews(commitId);
        if (cancelled) return;
        setData(result);
        setError(null);

        if (result.status === "pending" && attempts < MAX_POLLS) {
          attempts += 1;
          setPolls(attempts);
          timer = setTimeout(load, POLL_MS);
        }
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.detail : "Could not load the AI review.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    setPolls(0);
    load();

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [commitId, pollToken]);

  const rerun = async () => {
    setLoading(true);
    setError(null);
    try {
      await aiApi.rerunReview(commitId, false);
      setData((current) => (current ? { ...current, status: "pending" } : current));
      // Re-arm the polling effect; it will pick the fresh status up.
      setPollToken((value) => value + 1);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not start a new review.");
      setLoading(false);
    }
  };

  // ----------------------------------------------------------------- render
  const reviews = data?.reviews ?? [];
  const counts = reviews.reduce<Record<string, number>>((accumulator, review) => {
    accumulator[review.severity] = (accumulator[review.severity] ?? 0) + 1;
    return accumulator;
  }, {});

  return (
    <section className="card overflow-hidden" aria-label="AI code review">
      <header className="card-header">
        <h2 className="flex items-center gap-1.5 text-sm font-semibold">
          <Sparkles className="h-3.5 w-3.5 text-done" /> AI code review
        </h2>

        <div className="flex items-center gap-2 text-2xs">
          {renderStatus(data?.status, loading, polls)}
          {canRerun && (
            <button type="button" onClick={rerun} disabled={loading} className="btn h-6 text-2xs">
              <RefreshCw className={cn("h-3 w-3", loading && "animate-spin")} /> Re-run
            </button>
          )}
        </div>
      </header>

      {error && (
        <p className="flex items-center gap-2 border-b border-border bg-danger/10 px-4 py-2 text-2xs text-danger">
          <AlertCircle className="h-3.5 w-3.5 shrink-0" /> {error}
        </p>
      )}

      {data?.status === "failed" && data.error && (
        <p className="flex items-start gap-2 border-b border-border bg-attention/10 px-4 py-2 text-2xs text-attention">
          <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>
            The reviewer could not run: {data.error}
            <br />
            Start Ollama (<code>ollama serve</code>) and pull <code>llama3.2</code>, then re-run.
          </span>
        </p>
      )}

      {reviews.length > 0 && (
        <div className="flex flex-wrap gap-2 border-b border-border px-4 py-2 text-2xs text-fg-muted">
          {Object.entries(counts).map(([severity, count]) => (
            <span key={severity} className="inline-flex items-center gap-1">
              <span
                aria-hidden
                className="h-2 w-2 rounded-full"
                style={{ backgroundColor: SEVERITY_STYLES[severity]?.dot ?? "#8b949e" }}
              />
              {count} {severity}
            </span>
          ))}
        </div>
      )}

      {loading && reviews.length === 0 ? (
        <div className="space-y-3 p-4">
          {Array.from({ length: 3 }).map((_, index) => (
            <div key={index} className="space-y-1.5">
              <div className="h-3 w-48 skeleton" />
              <div className="h-3 w-full skeleton" />
              <div className="h-3 w-4/5 skeleton" />
            </div>
          ))}
        </div>
      ) : reviews.length === 0 ? (
        <div className="flex flex-col items-center gap-2 p-8 text-center">
          <ShieldAlert className="h-6 w-6 text-success" />
          <p className="text-sm font-medium">No issues found</p>
          <p className="max-w-md text-xs text-fg-muted">
            {data?.status === "complete"
              ? "Llama 3.2 reviewed this diff and found nothing worth flagging."
              : "The review has not completed yet."}
          </p>
        </div>
      ) : (
        <ul className="divide-y divide-border">
          {reviews.map((review) => {
            const style = SEVERITY_STYLES[review.severity] ?? SEVERITY_STYLES.Suggestion;
            return (
              <li key={review.id} className="p-4">
                <header className="mb-1.5 flex flex-wrap items-center gap-2">
                  <span className={cn("badge", style.className)}>{style.label}</span>
                  {review.file_path && (
                    <code className="text-2xs text-fg-muted">
                      {review.file_path}
                      {review.line_number ? `:${review.line_number}` : ""}
                    </code>
                  )}
                  {review.title && <span className="text-xs font-semibold">{review.title}</span>}
                </header>
                <p className="whitespace-pre-wrap text-xs leading-relaxed text-fg-muted">
                  {review.review_text}
                </p>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

function renderStatus(status: string | undefined, loading: boolean, polls: number) {
  if (loading && status === undefined) {
    return <span className="text-fg-muted">Loading…</span>;
  }
  switch (status) {
    case "pending":
      return (
        <span className="inline-flex items-center gap-1.5 text-attention">
          <span className="h-2 w-2 animate-pulse-dot rounded-full bg-attention" />
          Reviewing… {polls > 0 && `(${polls})`}
        </span>
      );
    case "complete":
      return (
        <span className="inline-flex items-center gap-1.5 text-success">
          <CheckCircle2 className="h-3.5 w-3.5" /> Complete
        </span>
      );
    case "failed":
      return (
        <span className="inline-flex items-center gap-1.5 text-danger">
          <AlertCircle className="h-3.5 w-3.5" /> Failed
        </span>
      );
    case "disabled":
      return <span className="text-fg-muted">AI disabled</span>;
    default:
      return <span className="text-fg-muted">—</span>;
  }
}
