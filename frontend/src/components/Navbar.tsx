"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import {
  ChevronDown,
  Github,
  LayoutDashboard,
  LogOut,
  Menu,
  Moon,
  Search,
  Sparkles,
  Sun,
  User as UserIcon,
  X,
} from "lucide-react";

import { useAuth } from "@/context/AuthContext";
import { cn, initials } from "@/lib/utils";

const NAV_LINKS = [
  { href: "/explore", label: "Explore" },
  { href: "/docs", label: "Docs" },
];

/**
 * Top navigation bar.
 *
 * GitHub-inspired: logo, a global search field, then auth-aware actions.
 * Also hosts the dark/light toggle, which flips a class on <html>.
 */
export function Navbar() {
  const { user, loading, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  const [query, setQuery] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [theme, setTheme] = useState<"dark" | "light">("dark");

  const menuRef = useRef<HTMLDivElement>(null);

  // ------------------------------------------------------------- theming
  useEffect(() => {
    const stored = (localStorage.getItem("gitfolio.theme") as "dark" | "light" | null) ?? "dark";
    setTheme(stored);
    document.documentElement.classList.toggle("light", stored === "light");
  }, []);

  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    localStorage.setItem("gitfolio.theme", next);
    document.documentElement.classList.toggle("light", next === "light");
  };

  // ------------------------------------------------- click-outside close
  useEffect(() => {
    function onClick(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  useEffect(() => {
    setMobileOpen(false);
    setMenuOpen(false);
  }, [pathname]);

  const submitSearch = (event: React.FormEvent) => {
    event.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) return;
    // `owner/repo` jumps straight to the repository, otherwise it is a user search.
    if (trimmed.includes("/")) {
      const [owner, repo] = trimmed.split("/");
      router.push(`/${owner}/${repo}`);
    } else {
      router.push(`/${trimmed}`);
    }
  };

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-canvas/85 backdrop-blur-md">
      <div className="mx-auto flex h-14 w-full max-w-7xl items-center gap-3 px-4 sm:px-6 lg:px-8">
        {/* Logo */}
        <Link href="/" className="flex shrink-0 items-center gap-2 font-semibold">
          <span className="grid h-7 w-7 place-items-center rounded-md bg-accent-emphasis text-fg-onEmphasis">
            <Github className="h-4 w-4" />
          </span>
          <span className="hidden text-sm tracking-tight sm:inline">GitFolio</span>
        </Link>

        {/* Global search */}
        <form onSubmit={submitSearch} className="relative hidden flex-1 md:block">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-fg-subtle" />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search users or owner/repo…"
            aria-label="Search GitFolio"
            className="w-full max-w-md rounded-md border border-border bg-canvas-inset py-1.5 pl-8 pr-3 text-sm
                       placeholder:text-fg-subtle focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent/40"
          />
        </form>

        <nav className="hidden items-center gap-1 md:flex">
          {NAV_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className={cn(
                "rounded-md px-2.5 py-1.5 text-sm text-fg-muted transition hover:bg-canvas-subtle hover:text-fg",
                pathname === link.href && "text-fg",
              )}
            >
              {link.label}
            </Link>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-1.5">
          <button
            type="button"
            onClick={toggleTheme}
            aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
            className="btn btn-ghost h-8 w-8 !px-0"
          >
            {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </button>

          {/* Mobile menu toggle */}
          <button
            type="button"
            onClick={() => setMobileOpen((open) => !open)}
            aria-label="Toggle navigation"
            className="btn btn-ghost h-8 w-8 !px-0 md:hidden"
          >
            {mobileOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
          </button>

          {loading ? (
            <div className="h-7 w-7 animate-pulse rounded-full bg-canvas-subtle" />
          ) : user ? (
            <div className="relative" ref={menuRef}>
              <button
                type="button"
                onClick={() => setMenuOpen((open) => !open)}
                aria-haspopup="menu"
                aria-expanded={menuOpen}
                className="flex items-center gap-1.5 rounded-full border border-border bg-canvas-subtle py-0.5 pl-0.5 pr-1.5 transition hover:border-fg-subtle"
              >
                <Avatar user={user} size={24} />
                <ChevronDown className="h-3 w-3 text-fg-muted" />
              </button>

              {menuOpen && (
                <div
                  role="menu"
                  className="absolute right-0 mt-2 w-56 animate-fade-in overflow-hidden rounded-lg border border-border bg-canvas-overlay p-1 shadow-popover"
                >
                  <div className="px-3 py-2">
                    <p className="truncate text-sm font-semibold">{user.display_name ?? user.username}</p>
                    <p className="truncate text-xs text-fg-muted">@{user.username}</p>
                  </div>
                  <div className="my-1 border-t border-border" />
                  <Link
                    href={`/${user.username}`}
                    className="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-fg-muted hover:bg-canvas-subtle hover:text-fg"
                    role="menuitem"
                  >
                    <UserIcon className="h-4 w-4" /> Your profile
                  </Link>
                  <Link
                    href="/dashboard"
                    className="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-fg-muted hover:bg-canvas-subtle hover:text-fg"
                    role="menuitem"
                  >
                    <LayoutDashboard className="h-4 w-4" /> Dashboard
                  </Link>
                  <button
                    type="button"
                    onClick={logout}
                    className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm text-danger hover:bg-danger/10"
                    role="menuitem"
                  >
                    <LogOut className="h-4 w-4" /> Sign out
                  </button>
                </div>
              )}
            </div>
          ) : (
            <>
              <Link href="/login" className="btn btn-ghost h-8 text-xs">
                Sign in
              </Link>
              <Link href="/register" className="btn btn-primary h-8 text-xs">
                <Sparkles className="h-3.5 w-3.5" />
                Create account
              </Link>
            </>
          )}
        </div>
      </div>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div className="animate-fade-in border-t border-border bg-canvas-subtle px-4 py-3 md:hidden">
          <form onSubmit={submitSearch} className="mb-3 md:hidden">
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search users or owner/repo…"
              className="input"
            />
          </form>
          <nav className="flex flex-col">
            {NAV_LINKS.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="rounded-md px-2 py-2 text-sm text-fg-muted hover:bg-canvas hover:text-fg"
              >
                {link.label}
              </Link>
            ))}
            {user && (
              <Link
                href="/dashboard"
                className="rounded-md px-2 py-2 text-sm text-fg-muted hover:bg-canvas hover:text-fg"
              >
                Dashboard
              </Link>
            )}
          </nav>
        </div>
      )}
    </header>
  );
}

/** Circular avatar with a graceful initials fallback. */
export function Avatar({
  user,
  size = 32,
  className,
}: {
  user: { username: string; avatar_url: string | null };
  size?: number;
  className?: string;
}) {
  const [failed, setFailed] = useState(false);

  if (!user.avatar_url || failed) {
    return (
      <span
        style={{ width: size, height: size, fontSize: Math.max(9, size * 0.38) }}
        className={cn(
          "grid shrink-0 place-items-center rounded-full bg-accent-emphasis font-semibold text-fg-onEmphasis",
          className,
        )}
      >
        {initials(user.username)}
      </span>
    );
  }

  return (
    <img
      src={user.avatar_url}
      alt={`${user.username}'s avatar`}
      width={size}
      height={size}
      onError={() => setFailed(true)}
      style={{ width: size, height: size }}
      className={cn("shrink-0 rounded-full border border-border object-cover", className)}
    />
  );
}
