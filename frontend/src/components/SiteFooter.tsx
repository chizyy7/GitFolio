import Link from "next/link";
import { Cpu, Database, Github, Sparkles } from "lucide-react";

/** Static footer — also a reminder of the local-only AI stack. */
export function SiteFooter() {
  return (
    <footer className="mt-12 border-t border-border bg-canvas-subtle">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-4 px-4 py-8 sm:px-6 lg:px-8 md:flex-row md:items-center md:justify-between">
        <div className="flex items-center gap-2 text-sm text-fg-muted">
          <Github className="h-4 w-4" />
          <span>
            <span className="font-semibold text-fg">GitFolio</span> — AI-powered version control
            and portfolio platform.
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-4 text-xs text-fg-muted">
          <span className="inline-flex items-center gap-1.5">
            <Cpu className="h-3.5 w-3.5 text-success" /> Llama 3.2 via Ollama
          </span>
          <span className="inline-flex items-center gap-1.5">
            <Database className="h-3.5 w-3.5 text-accent" /> ChromaDB vectors
          </span>
          <span className="inline-flex items-center gap-1.5">
            <Sparkles className="h-3.5 w-3.5 text-done" /> 100% local — no paid APIs
          </span>
          <Link href="/docs" className="link">
            API docs
          </Link>
        </div>
      </div>
    </footer>
  );
}
