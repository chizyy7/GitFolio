"use client";

import Link from "next/link";
import { Lock, Loader2 } from "lucide-react";

import { useAuth } from "@/context/AuthContext";
import type { UserMe } from "@/lib/types";

/**
 * Centred loading indicator used while a page fetches its data.
 */
export function PageLoader({ label = "Loading…" }: { label?: string }) {
  return (
    <div
      role="status"
      aria-live="polite"
      className="flex min-h-[40vh] flex-col items-center justify-center gap-3 text-sm text-fg-muted"
    >
      <Loader2 className="h-6 w-6 animate-spin text-accent" />
      <span>{label}</span>
    </div>
  );
}

/**
 * Friendly error panel used by pages whose primary fetch failed.
 */
export function ErrorPanel({
  title = "Something went wrong",
  message,
  onRetry,
}: {
  title?: string;
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="card mx-auto max-w-lg p-6 text-center">
      <h1 className="text-sm font-semibold">{title}</h1>
      <p className="mt-2 text-xs text-fg-muted">{message}</p>
      {onRetry && (
        <button type="button" onClick={onRetry} className="btn mx-auto mt-4 text-xs">
          Try again
        </button>
      )}
    </div>
  );
}

/**
 * Gate for signed-in-only pages.
 *
 * Renders a loading state while the session hydrates, a sign-in prompt when
 * unauthenticated, and otherwise calls `children` with the resolved user.
 */
export function RequireAuth({
  children,
  message = "You need to be signed in to view this page.",
}: {
  children: (user: UserMe) => React.ReactNode;
  message?: string;
}) {
  const { user, loading } = useAuth();

  if (loading) return <PageLoader label="Checking your session…" />;

  if (!user) {
    return (
      <div className="card mx-auto max-w-md p-8 text-center">
        <span className="mx-auto mb-3 grid h-11 w-11 place-items-center rounded-full border border-border bg-canvas text-fg-muted">
          <Lock className="h-5 w-5" />
        </span>
        <h1 className="text-sm font-semibold">Sign in required</h1>
        <p className="mx-auto mt-2 max-w-xs text-xs text-fg-muted">{message}</p>
        <div className="mt-5 flex justify-center gap-2">
          <Link href="/login" className="btn btn-primary text-xs">
            Sign in
          </Link>
          <Link href="/register" className="btn text-xs">
            Create account
          </Link>
        </div>
      </div>
    );
  }

  return <>{children(user)}</>;
}
