import Link from "next/link";
import {
  Bot,
  GitBranch,
  GitCommitHorizontal,
  Cpu,
  Database,
  Fingerprint,
  Gauge,
  Search,
  ShieldCheck,
  Sparkles,
  Upload,
} from "lucide-react";

const siteName = process.env.NEXT_PUBLIC_SITE_NAME ?? "GitFolio";

/**
 * Marketing landing page.
 *
 * A server component on purpose: it is fully static, so it ships zero JS and
 * doubles as the SEO entry point. The interactive pieces live on the pages it
 * links to.
 */
export default function HomePage() {
  return (
    <div className="space-y-20 pb-8">
      {/* ------------------------------------------------------------- hero */}
      <section className="relative overflow-hidden rounded-2xl border border-border bg-canvas-subtle px-6 py-16 sm:px-12 sm:py-24">
        <div aria-hidden className="grid-backdrop pointer-events-none absolute inset-0" />

        <div className="relative mx-auto max-w-3xl text-center">
          <span className="badge mx-auto border-done/40 bg-done/10 text-done">
            <Sparkles className="h-3 w-3" /> 100% local AI · no paid APIs
          </span>

          <h1 className="mt-5 text-4xl font-bold tracking-tight sm:text-5xl">
            Your code. Your history.
            <span className="block bg-gradient-to-r from-accent to-done bg-clip-text text-transparent">
              An AI that actually understands it.
            </span>
          </h1>

          <p className="mx-auto mt-5 max-w-2xl text-sm leading-relaxed text-fg-muted sm:text-base">
            {siteName} is a self-hosted version-control and developer-portfolio platform.
            Push real Git commits, then let a local{" "}
            <span className="text-fg">Llama 3.2</span> explain your repository, review every
            diff, write commit messages and answer questions about your own code.
          </p>

          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <Link href="/register" className="btn btn-primary px-5 py-2.5 text-sm">
              <Sparkles className="h-4 w-4" /> Start building your portfolio
            </Link>
            <Link href="/explore" className="btn px-5 py-2.5 text-sm">
              <Search className="h-4 w-4" /> Explore developers
            </Link>
          </div>

          <p className="mt-4 text-2xs text-fg-subtle">
            Runs entirely on your machine — PostgreSQL, ChromaDB and Ollama.
          </p>
        </div>
      </section>

      {/* ---------------------------------------------------------- pillars */}
      <section className="grid gap-4 md:grid-cols-3">
        <Pillar
          icon={<GitBranch className="h-5 w-5" />}
          accent="border-accent/30 bg-accent/10 text-accent"
          title="Real version control"
          body="Every push creates a genuine pygit2 commit with a SHA-1 hash, parent, author and a unified diff stored for browsing."
        />
        <Pillar
          icon={<Bot className="h-5 w-5" />}
          accent="border-done/30 bg-done/10 text-done"
          title="AI that reads your repo"
          body="Code is chunked along AST boundaries and embedded into ChromaDB, so retrieval answers cite the exact file and line."
        />
        <Pillar
          icon={<ShieldCheck className="h-5 w-5" />}
          accent="border-success/30 bg-success/10 text-success"
          title="Reviews & skills"
          body="Llama 3.2 flags bugs, security issues and style problems on every commit, and profiles your stack into skill badges."
        />
      </section>

      {/* --------------------------------------------------------- features */}
      <section>
        <header className="mb-6 text-center">
          <h2 className="text-2xl font-bold tracking-tight">Everything a developer portfolio needs</h2>
          <p className="mt-2 text-sm text-fg-muted">
            A GitHub-style experience, rebuilt around a private, local AI stack.
          </p>
        </header>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Feature
            icon={<GitCommitHorizontal className="h-4 w-4" />}
            title="Commit history & diffs"
            body="Browse history, inspect split diffs and jump between revisions — all rendered server-side with syntax highlighting."
          />
          <Feature
            icon={<Bot className="h-4 w-4" />}
            title="Ask your codebase"
            body="RAG chat retrieves the most relevant functions and explains them, with clickable citations that open the file at the right line."
          />
          <Feature
            icon={<Search className="h-4 w-4" />}
            title="Semantic search"
            body="Search by intent, not substring: 'function that hashes a password' finds hash_password even when the words never appear."
          />
          <Feature
            icon={<Sparkles className="h-4 w-4" />}
            title="Auto commit messages"
            body="Leave the message blank and the model writes a conventional-commit summary straight from the diff."
          />
          <Feature
            icon={<Gauge className="h-4 w-4" />}
            title="Contribution heatmap"
            body="A GitHub-style activity grid with streaks, weekly trends and a language doughnut — all powered by Recharts."
          />
          <Feature
            icon={<Upload className="h-4 w-4" />}
            title="Push from anywhere"
            body="Seed repositories from the browser or push a folder from your machine with the bundled CLI."
          />
        </div>
      </section>

      {/* ------------------------------------------------------------- stack */}
      <section className="card overflow-hidden">
        <div className="grid gap-6 p-6 sm:p-8 md:grid-cols-2">
          <div>
            <h2 className="text-lg font-semibold">Built on an open, local-first stack</h2>
            <p className="mt-2 text-sm leading-relaxed text-fg-muted">
              No OpenAI, no Anthropic, no per-token billing. The intelligence layer runs on
              your hardware with models you can inspect and swap.
            </p>
            <div className="mt-5 flex flex-wrap gap-2">
              {["Next.js 14", "FastAPI", "PostgreSQL", "ChromaDB", "Ollama", "pygit2", "tree-sitter"].map(
                (tech) => (
                  <span key={tech} className="chip">
                    {tech}
                  </span>
                ),
              )}
            </div>
          </div>

          <ul className="grid gap-3 sm:grid-cols-2">
            <StackItem icon={<Cpu className="h-4 w-4" />} label="Llama 3.2 via Ollama" />
            <StackItem icon={<Database className="h-4 w-4" />} label="nomic-embed-text vectors" />
            <StackItem icon={<Fingerprint className="h-4 w-4" />} label="JWT OAuth2 auth" />
            <StackItem icon={<ShieldCheck className="h-4 w-4" />} label="Private by default" />
          </ul>
        </div>
      </section>

      {/* -------------------------------------------------------------- CTA */}
      <section className="rounded-2xl border border-border bg-gradient-to-b from-canvas-subtle to-canvas px-6 py-12 text-center">
        <h2 className="text-2xl font-bold tracking-tight">Ready to see your code explained?</h2>
        <p className="mx-auto mt-2 max-w-xl text-sm text-fg-muted">
          Create an account, push your first repository and ask the AI anything about it.
        </p>
        <div className="mt-6 flex flex-wrap justify-center gap-3">
          <Link href="/register" className="btn btn-primary px-5 py-2.5 text-sm">
            Create your account
          </Link>
          <Link href="/docs" className="btn px-5 py-2.5 text-sm">
            Read the docs
          </Link>
        </div>
      </section>
    </div>
  );
}

function Pillar({
  icon,
  accent,
  title,
  body,
}: {
  icon: React.ReactNode;
  accent: string;
  title: string;
  body: string;
}) {
  return (
    <article className="card p-5">
      <span className={`grid h-10 w-10 place-items-center rounded-md border ${accent}`}>{icon}</span>
      <h3 className="mt-3 text-sm font-semibold">{title}</h3>
      <p className="mt-1.5 text-xs leading-relaxed text-fg-muted">{body}</p>
    </article>
  );
}

function Feature({
  icon,
  title,
  body,
}: {
  icon: React.ReactNode;
  title: string;
  body: string;
}) {
  return (
    <article className="card flex gap-3 p-4">
      <span className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-md border border-border bg-canvas text-fg-muted">
        {icon}
      </span>
      <div>
        <h3 className="text-sm font-semibold">{title}</h3>
        <p className="mt-1 text-xs leading-relaxed text-fg-muted">{body}</p>
      </div>
    </article>
  );
}

function StackItem({ icon, label }: { icon: React.ReactNode; label: string }) {
  return (
    <li className="flex items-center gap-2 rounded-md border border-border bg-canvas px-3 py-2 text-xs text-fg-muted">
      <span className="text-accent">{icon}</span>
      {label}
    </li>
  );
}
