import Link from "next/link";
import { Compass, Home, SearchX } from "lucide-react";

/**
 * Global 404 page, rendered for unmatched routes and `notFound()` calls.
 */
export default function NotFound() {
  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center text-center">
      <span className="grid h-14 w-14 place-items-center rounded-full border border-border bg-canvas text-fg-muted">
        <SearchX className="h-6 w-6" />
      </span>
      <p className="mt-4 font-mono text-2xs uppercase tracking-widest text-fg-subtle">404</p>
      <h1 className="mt-1 text-xl font-bold tracking-tight">This page could not be found</h1>
      <p className="mt-2 max-w-sm text-sm text-fg-muted">
        The page you are looking for does not exist, or it may have moved.
      </p>
      <div className="mt-6 flex gap-2">
        <Link href="/" className="btn btn-primary text-xs">
          <Home className="h-3.5 w-3.5" /> Go home
        </Link>
        <Link href="/explore" className="btn text-xs">
          <Compass className="h-3.5 w-3.5" /> Explore developers
        </Link>
      </div>
    </div>
  );
}
