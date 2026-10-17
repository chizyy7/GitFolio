"use client";

import { useEffect } from "react";
import { AlertTriangle, Home, RotateCw } from "lucide-react";
import Link from "next/link";

/**
 * Route-level error boundary.
 *
 * Next.js renders this when a page throws during render. `reset()` re-attempts
 * the segment, which is the right action for the transient API failures this app
 * can hit when the backend is still starting.
 */
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Surface the error in the browser console for debugging.
    console.error(error);
  }, [error]);

  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center text-center">
      <span className="grid h-14 w-14 place-items-center rounded-full border border-danger/40 bg-danger/10 text-danger">
        <AlertTriangle className="h-6 w-6" />
      </span>
      <h1 className="mt-4 text-xl font-bold tracking-tight">Something went wrong</h1>
      <p className="mt-2 max-w-md text-sm text-fg-muted">
        An unexpected error occurred while rendering this page.
        {error.message && (
          <>
            {" "}
            <span className="text-fg-subtle">({error.message})</span>
          </>
        )}
      </p>
      <div className="mt-6 flex gap-2">
        <button type="button" onClick={reset} className="btn btn-primary text-xs">
          <RotateCw className="h-3.5 w-3.5" /> Try again
        </button>
        <Link href="/" className="btn text-xs">
          <Home className="h-3.5 w-3.5" /> Go home
        </Link>
      </div>
    </div>
  );
}
