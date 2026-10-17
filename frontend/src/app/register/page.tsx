"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { AlertCircle, Check, Github, Loader2, Sparkles, X } from "lucide-react";

import { ApiError, authApi } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { cn } from "@/lib/utils";

type Availability = "idle" | "checking" | "available" | "taken" | "invalid";

const USERNAME_PATTERN = /^[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,37}[a-zA-Z0-9])?$/;

/**
 * Registration form.
 *
 * Includes a debounced username-availability probe so a visitor learns about a
 * clash before submitting, and a client-side password confirmation.
 */
export default function RegisterPage() {
  const router = useRouter();
  const { user, loading, register } = useAuth();

  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");

  const [availability, setAvailability] = useState<Availability>("idle");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const timerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => {
    if (!loading && user) router.replace("/dashboard");
  }, [loading, user, router]);

  // Debounced username availability check.
  useEffect(() => {
    const value = username.trim();
    if (timerRef.current) clearTimeout(timerRef.current);

    if (value.length < 3) {
      setAvailability(value.length === 0 ? "idle" : "invalid");
      return;
    }
    if (!USERNAME_PATTERN.test(value)) {
      setAvailability("invalid");
      return;
    }

    setAvailability("checking");
    timerRef.current = setTimeout(async () => {
      try {
        const result = await authApi.checkUsername(value);
        setAvailability(result.available ? "available" : "taken");
      } catch {
        // Don't block registration if the probe itself fails.
        setAvailability("idle");
      }
    }, 400);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [username]);

  const passwordsMatch = password.length === 0 || password === confirm;
  const canSubmit =
    username.trim().length >= 3 &&
    availability !== "taken" &&
    availability !== "invalid" &&
    email.trim().length > 3 &&
    password.length >= 8 &&
    passwordsMatch;

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!canSubmit) return;
    setSubmitting(true);
    setError(null);
    try {
      await register({
        username: username.trim(),
        email: email.trim(),
        password,
        display_name: displayName.trim() || undefined,
      });
      router.push("/dashboard");
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.fieldErrors.length
            ? err.fieldErrors.map((field) => field.message).join(" ")
            : err.detail
          : "Could not create your account.";
      setError(message);
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
        <h1 className="mt-3 text-lg font-semibold">Create your GitFolio account</h1>
        <p className="mt-1 text-xs text-fg-muted">
          Claim your username and start building an AI-reviewed portfolio.
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
          <span className="mb-1 block text-xs font-medium text-fg-muted">
            Username <span className="text-danger">*</span>
          </span>
          <div className="relative">
            <input
              required
              autoComplete="username"
              value={username}
              onChange={(event) => setUsername(event.target.value.replace(/\s/g, ""))}
              placeholder="octocat"
              className="input pr-9"
            />
            <span className="absolute right-2.5 top-1/2 -translate-y-1/2">
              <AvailabilityIcon state={availability} />
            </span>
          </div>
          <span className="mt-1 block text-2xs">
            {availability === "taken" ? (
              <span className="text-danger">That username is already taken.</span>
            ) : availability === "invalid" ? (
              <span className="text-attention">
                3–39 characters: letters, numbers, hyphens and underscores.
              </span>
            ) : availability === "available" ? (
              <span className="text-success">@{username.trim()} is available.</span>
            ) : (
              <span className="text-fg-subtle">This becomes your profile URL.</span>
            )}
          </span>
        </label>

        <label className="block">
          <span className="mb-1 block text-xs font-medium text-fg-muted">Display name</span>
          <input
            value={displayName}
            onChange={(event) => setDisplayName(event.target.value)}
            placeholder="Ada Lovelace"
            className="input"
          />
        </label>

        <label className="block">
          <span className="mb-1 block text-xs font-medium text-fg-muted">
            Email <span className="text-danger">*</span>
          </span>
          <input
            required
            type="email"
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="you@example.com"
            className="input"
          />
        </label>

        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-fg-muted">
              Password <span className="text-danger">*</span>
            </span>
            <input
              required
              type="password"
              autoComplete="new-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="At least 8 characters"
              className="input"
            />
          </label>

          <label className="block">
            <span className="mb-1 block text-xs font-medium text-fg-muted">
              Confirm password <span className="text-danger">*</span>
            </span>
            <input
              required
              type="password"
              autoComplete="new-password"
              value={confirm}
              onChange={(event) => setConfirm(event.target.value)}
              placeholder="Repeat password"
              className={cn("input", !passwordsMatch && "border-danger focus:border-danger")}
            />
          </label>
        </div>

        {!passwordsMatch && <p className="text-2xs text-danger">Passwords do not match.</p>}

        <button type="submit" disabled={submitting || !canSubmit} className="btn btn-primary w-full text-sm">
          <Sparkles className="h-4 w-4" />
          {submitting ? "Creating your account…" : "Create account"}
        </button>

        <p className="text-center text-xs text-fg-muted">
          Already have an account?{" "}
          <Link href="/login" className="link">
            Sign in
          </Link>
        </p>
      </form>
    </div>
  );
}

function AvailabilityIcon({ state }: { state: Availability }) {
  switch (state) {
    case "checking":
      return <Loader2 className="h-4 w-4 animate-spin text-fg-subtle" />;
    case "available":
      return <Check className="h-4 w-4 text-success" />;
    case "taken":
    case "invalid":
      return <X className="h-4 w-4 text-danger" />;
    default:
      return null;
  }
}
