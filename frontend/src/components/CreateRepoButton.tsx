"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Plus, X } from "lucide-react";

import { ApiError, reposApi } from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * "New repository" button + modal.
 *
 * Creating a repository immediately materialises its Git object database on
 * the backend, so a push works straight away.
 */
export function CreateRepoButton() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [visibility, setVisibility] = useState<"Public" | "Private">("Public");
  const [topics, setTopics] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const repo = await reposApi.create({
        name: name.trim(),
        description: description.trim() || null,
        visibility,
        topics: topics
          .split(",")
          .map((topic) => topic.trim())
          .filter(Boolean),
        auto_index: true,
      });
      setOpen(false);
      setName("");
      setDescription("");
      setTopics("");
      router.push(`/${repo.owner_username}/${repo.name}`);
      router.refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not create the repository.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <button type="button" onClick={() => setOpen(true)} className="btn h-7 text-2xs">
        <Plus className="h-3 w-3" /> New
      </button>

      {open && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Create a new repository"
          className="fixed inset-0 z-50 grid place-items-center bg-canvas-inset/70 p-4 backdrop-blur-sm"
          onClick={(event) => {
            if (event.target === event.currentTarget) setOpen(false);
          }}
        >
          <form
            onSubmit={submit}
            className="w-full max-w-md animate-fade-in rounded-xl border border-border bg-canvas-subtle p-5 shadow-popover"
          >
            <header className="mb-4 flex items-center justify-between">
              <h2 className="text-sm font-semibold">Create a new repository</h2>
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="btn btn-ghost h-7 w-7 !px-0"
                aria-label="Close"
              >
                <X className="h-4 w-4" />
              </button>
            </header>

            <div className="space-y-3">
              <label className="block">
                <span className="mb-1 block text-xs font-medium text-fg-muted">
                  Repository name <span className="text-danger">*</span>
                </span>
                <input
                  required
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  placeholder="my-awesome-project"
                  pattern="[A-Za-z0-9._-]+"
                  className="input"
                />
                <span className="mt-1 block text-2xs text-fg-subtle">
                  Letters, numbers, hyphens, underscores and dots.
                </span>
              </label>

              <label className="block">
                <span className="mb-1 block text-xs font-medium text-fg-muted">Description</span>
                <textarea
                  value={description}
                  onChange={(event) => setDescription(event.target.value)}
                  rows={3}
                  maxLength={2000}
                  placeholder="What is this project about?"
                  className="input resize-none"
                />
              </label>

              <label className="block">
                <span className="mb-1 block text-xs font-medium text-fg-muted">
                  Topics <span className="text-fg-subtle">(comma separated)</span>
                </span>
                <input
                  value={topics}
                  onChange={(event) => setTopics(event.target.value)}
                  placeholder="fastapi, nextjs, ai"
                  className="input"
                />
              </label>

              <fieldset>
                <legend className="mb-1 text-xs font-medium text-fg-muted">Visibility</legend>
                <div className="flex gap-2">
                  {(["Public", "Private"] as const).map((option) => (
                    <button
                      key={option}
                      type="button"
                      onClick={() => setVisibility(option)}
                      className={cn(
                        "btn flex-1 text-xs",
                        visibility === option && "border-accent bg-accent/10 text-accent",
                      )}
                    >
                      {option}
                    </button>
                  ))}
                </div>
              </fieldset>

              {error && <p className="text-xs text-danger">{error}</p>}
            </div>

            <footer className="mt-5 flex justify-end gap-2">
              <button type="button" onClick={() => setOpen(false)} className="btn text-xs">
                Cancel
              </button>
              <button
                type="submit"
                disabled={submitting || !name.trim()}
                className="btn btn-primary text-xs"
              >
                {submitting ? "Creating…" : "Create repository"}
              </button>
            </footer>
          </form>
        </div>
      )}
    </>
  );
}
