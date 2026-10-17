"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AlertCircle, Github, KeyRound, LogIn } from "lucide-react";

import { useAuth } from "@/context/AuthContext";
import { cn } from "@/lib/utils";

/**
 * Sign-in form.
 *
 * On success the token is stored by the auth context and the user is sent to
 * their dashboard. Already-authenticated visitors are redirected away.
 */
export default function LoginPage() {
  const router = useRouter();
  const { user, loading, login } = useAuth();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && user) router.replace("/dashboard");
  }, [loading, user, router]);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await login(username.trim(), password);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not sign you in.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto max-w-md py-8">
      <div className="mb-6 text-center">
        <span className="mx-auto grid h-10 w-10 place-items-center rounded-md bg-accent-emphasis text-fg-onEmphasis">
          <Github className="h-5 w-5" />
        </span>
        <h1 className="mt-3 text-lg font-semibold">Sign in to GitFolio</h1>
        <p className="mt-1 text-xs text-fg-muted">
          Welcome back. Your repositories and AI reviews are waiting.
        </p>
      </div>

      <form onSubmit={submit} className="card space-y-4 p-5">
        {error && (
          <p className="flex items-start gap-2 rounded-md border border-danger/40 bg-danger/10 px-3 py-2 text-xs text-danger">
            <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <span>{error}</span>
          </p>
        )}

        <label className="block">
          <span className="mb-1 block text-xs font-medium text-fg-muted">Username or email</span>
          <input
            required
            autoComplete="username"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            placeholder="octocat"
            className="input"
          />
        </label>

        <label className="block">
          <span className="mb-1 block text-xs font-medium text-fg-muted">Password</span>
          <input
            required
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="••••••••"
            className="input"
          />
        </label>

        <button
          type="submit"
          disabled={submitting || !username.trim() || !password}
          className={cn("btn btn-primary w-full text-sm")}
        >
          <LogIn className="h-4 w-4" />
          {submitting ? "Signing in…" : "Sign in"}
        </button>

        <p className="text-center text-xs text-fg-muted">
          New to GitFolio?{" "}
          <Link href="/register" className="link">
            Create an account
          </Link>
        </p>
      </form>

      <p className="mt-4 flex items-center justify-center gap-1.5 text-2xs text-fg-subtle">
        <KeyRound className="h-3 w-3" /> Sessions are secured with signed JWTs stored locally.
      </p>
    </div>
  );
}
