import type { Metadata } from "next";
import Link from "next/link";
import { BookOpen, Boxes, Cpu, Rocket, Terminal, Workflow } from "lucide-react";

export const metadata: Metadata = {
  title: "Documentation",
  description: "Set up, run and integrate GitFolio — a self-hosted, AI-powered version control platform.",
};

/**
 * Static documentation page.
 *
 * A server component: no client JS, and every section is plain markup so it can
 * be crawled and read without the interactive app.
 */
export default function DocsPage() {
  return (
    <div className="mx-auto max-w-4xl space-y-10 pb-8">
      <header>
        <h1 className="flex items-center gap-2 text-2xl font-bold tracking-tight">
          <BookOpen className="h-6 w-6 text-accent" /> Documentation
        </h1>
        <p className="mt-2 text-sm text-fg-muted">
          Everything you need to run GitFolio locally or deploy it, push code and wire the
          version-control API into your own tools.
        </p>
      </header>

      <nav aria-label="Sections" className="flex flex-wrap gap-2">
        {[
          ["#quickstart", "Quick start"],
          ["#architecture", "Architecture"],
          ["#ai", "The AI pipeline"],
          ["#cli", "Push from the CLI"],
          ["#api", "API reference"],
          ["#env", "Configuration"],
        ].map(([href, label]) => (
          <a key={href} href={href} className="chip">
            {label}
          </a>
        ))}
      </nav>

      {/* ------------------------------------------------------- quickstart */}
      <Section id="quickstart" icon={<Rocket className="h-5 w-5" />} title="Quick start">
        <p>
          The fastest path is Docker Compose, which brings up PostgreSQL, ChromaDB, Ollama, the
          FastAPI backend and the Next.js frontend together.
        </p>
        <Pre>{`# 1. Configure the environment
cp .env.example .env          # then set JWT_SECRET

# 2. Start the stack
docker compose up --build

# 3. Pull the models (first run only)
docker compose exec ollama ollama pull llama3.2
docker compose exec ollama ollama pull nomic-embed-text`}</Pre>
        <p className="text-xs text-fg-muted">
          Frontend on <code>http://localhost:3000</code>, API on{" "}
          <code>http://localhost:8000</code>, interactive docs on{" "}
          <code>http://localhost:8000/docs</code>.
        </p>

        <h3 className="pt-2 text-sm font-semibold">Local (without Docker)</h3>
        <Pre>{`# Backend
cd backend
python -m venv .venv && . .venv/bin/activate    # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev`}</Pre>
        <p className="text-xs text-fg-muted">
          The backend reads <code>.env</code> from its own folder or the repo root. Ollama and
          ChromaDB must be running for the AI features; without them the app degrades gracefully.
        </p>
      </Section>

      {/* ----------------------------------------------------- architecture */}
      <Section id="architecture" icon={<Boxes className="h-5 w-5" />} title="Architecture">
        <ul className="space-y-2">
          <Bullet term="Next.js 14 (App Router)">
            Server and client components. Syntax highlighting runs on the server via a route
            handler; heatmaps and charts are client-side Recharts.
          </Bullet>
          <Bullet term="FastAPI + SQLAlchemy">
            REST API with JWT (OAuth2 password-bearer) auth. PostgreSQL is the source of truth for
            users, repositories, commits, files, AI reviews and skills.
          </Bullet>
          <Bullet term="pygit2 object store">
            Each repository gets a bare Git object database on disk. Pushes create real commits
            with SHA-1 identities and parents; unified diffs are generated deterministically.
          </Bullet>
          <Bullet term="ChromaDB + Ollama">
            Code is chunked along AST boundaries (tree-sitter), embedded with{" "}
            <code>nomic-embed-text</code> and stored per repository. Retrieval feeds Llama 3.2.
          </Bullet>
        </ul>
      </Section>

      {/* --------------------------------------------------------------- AI */}
      <Section id="ai" icon={<Cpu className="h-5 w-5" />} title="The AI pipeline">
        <p>
          After every push, a background pipeline runs four jobs and each one degrades
          independently if the model stack is unavailable:
        </p>
        <ol className="ml-5 list-decimal space-y-1.5 text-sm text-fg-muted">
          <li>
            <strong className="text-fg">Ingestion</strong> — changed files are chunked, embedded
            and upserted into the repository&apos;s ChromaDB collection.
          </li>
          <li>
            <strong className="text-fg">Review</strong> — the unified diff is sent to Llama 3.2
            with a strict rubric; issues are stored with severity, file and line.
          </li>
          <li>
            <strong className="text-fg">Commit message</strong> — when none is supplied, one is
            written from the diff (with a deterministic fallback).
          </li>
          <li>
            <strong className="text-fg">Skills</strong> — file extensions and dependency manifests
            are profiled into proficiency-tagged skill badges.
          </li>
        </ol>
        <p className="text-xs text-fg-muted">
          Chat and search are retrieval-augmented: the top-K chunks are injected into the prompt
          and the answer comes back with citations you can click to jump to the exact line.
        </p>
      </Section>

      {/* -------------------------------------------------------------- CLI */}
      <Section id="cli" icon={<Terminal className="h-5 w-5" />} title="Push from the CLI">
        <p>
          The bundled CLI walks a local directory, filters build artefacts and posts the files as a
          single commit — the same endpoint the web Push panel uses.
        </p>
        <Pre>{`# Grab an access token by signing in
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \\
  -H 'Content-Type: application/json' \\
  -d '{"username":"you","password":"secret"}' | jq -r .access_token)

# Push the current directory to an existing repository
python cli/gitfolio.py push ./my-project \\
  --api http://localhost:8000/api \\
  --token "$TOKEN" \\
  --repo <repository-id> \\
  --message "feat: initial import"`}</Pre>
        <p className="text-xs text-fg-muted">
          Omit <code>--message</code> to let the Auto-Commit Message Generator write it. Use{" "}
          <code>--delete old/path.py</code> to remove files, and <code>--dry-run</code> to preview.
        </p>
      </Section>

      {/* -------------------------------------------------------------- API */}
      <Section id="api" icon={<Workflow className="h-5 w-5" />} title="API reference">
        <p className="text-xs text-fg-muted">
          All routes are prefixed with <code>/api</code> and expect a{" "}
          <code>Authorization: Bearer &lt;token&gt;</code> header where noted. The full OpenAPI
          schema lives at <code>/docs</code>.
        </p>
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left text-xs">
            <thead>
              <tr className="border-b border-border text-2xs uppercase tracking-wide text-fg-subtle">
                <th className="py-2 pr-4 font-medium">Method</th>
                <th className="py-2 pr-4 font-medium">Path</th>
                <th className="py-2 font-medium">Description</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {API_ROUTES.map((route) => (
                <tr key={`${route.method} ${route.path}`}>
                  <td className="py-2 pr-4">
                    <span className="badge border-border bg-canvas text-fg-muted">{route.method}</span>
                  </td>
                  <td className="py-2 pr-4">
                    <code className="font-mono text-accent">{route.path}</code>
                  </td>
                  <td className="py-2 text-fg-muted">{route.description}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      {/* -------------------------------------------------------------- env */}
      <Section id="env" icon={<Cpu className="h-5 w-5" />} title="Configuration">
        <p className="text-xs text-fg-muted">
          Copy <code>.env.example</code> to <code>.env</code> and adjust. The most important
          variables:
        </p>
        <dl className="grid gap-2 sm:grid-cols-2">
          {ENV_VARS.map(([name, description]) => (
            <div key={name} className="rounded-md border border-border bg-canvas p-3">
              <dt>
                <code className="text-xs text-accent">{name}</code>
              </dt>
              <dd className="mt-1 text-2xs text-fg-muted">{description}</dd>
            </div>
          ))}
        </dl>
      </Section>

      <section className="card flex flex-wrap items-center justify-between gap-3 p-5">
        <p className="text-sm text-fg-muted">Ready to try it?</p>
        <div className="flex gap-2">
          <Link href="/register" className="btn btn-primary text-xs">
            Create an account
          </Link>
          <Link href="/explore" className="btn text-xs">
            Explore developers
          </Link>
        </div>
      </section>
    </div>
  );
}

const API_ROUTES: { method: string; path: string; description: string }[] = [
  { method: "POST", path: "/auth/register", description: "Create an account and receive a token." },
  { method: "POST", path: "/auth/login", description: "OAuth2 password flow — returns a JWT." },
  { method: "GET", path: "/auth/me", description: "The current, authenticated user." },
  { method: "GET", path: "/users", description: "List accounts (developer directory)." },
  { method: "GET", path: "/users/{username}", description: "Public profile with skills and stats." },
  { method: "GET", path: "/repos/{username}", description: "List a user's repositories." },
  { method: "POST", path: "/repos", description: "Create a repository." },
  { method: "GET", path: "/repos/{username}/{repo}", description: "Repository detail + file tree." },
  { method: "POST", path: "/repos/{id}/push", description: "Push files and create a commit." },
  { method: "GET", path: "/repos/{id}/commits", description: "Paginated commit history." },
  { method: "GET", path: "/repos/{id}/commits/{hash}", description: "Commit diff and AI review." },
  { method: "POST", path: "/ai/chat", description: "RAG chat over the repository's code." },
  { method: "POST", path: "/ai/search", description: "Semantic code search." },
  { method: "GET", path: "/ai/reviews/{commit}", description: "AI review for a commit." },
  { method: "POST", path: "/ai/index/{repo}", description: "Embed a repository for search." },
  { method: "GET", path: "/dashboard/{username}", description: "Heatmap, activity and stats." },
];

const ENV_VARS: [string, string][] = [
  ["DATABASE_URL", "PostgreSQL connection string (use the +psycopg driver)."],
  ["JWT_SECRET", "Long random string used to sign access tokens."],
  ["OLLAMA_HOST", "Where Ollama listens (default http://localhost:11434)."],
  ["OLLAMA_CHAT_MODEL", "Chat model, e.g. llama3.2."],
  ["OLLAMA_EMBED_MODEL", "Embedding model, e.g. nomic-embed-text."],
  ["CHROMA_HOST / CHROMA_PORT", "ChromaDB server location."],
  ["STORAGE_PATH", "Directory holding the bare Git object databases."],
  ["AI_ENABLED", "Set false to run purely as version control."],
  ["NEXT_PUBLIC_API_URL", "Frontend → backend base URL (in frontend/.env.local)."],
];

function Section({
  id,
  icon,
  title,
  children,
}: {
  id: string;
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section id={id} className="scroll-mt-20 space-y-3">
      <h2 className="flex items-center gap-2 border-b border-border pb-2 text-lg font-semibold">
        <span className="text-accent">{icon}</span>
        {title}
      </h2>
      <div className="space-y-3 text-sm leading-relaxed text-fg-muted">{children}</div>
    </section>
  );
}

function Pre({ children }: { children: React.ReactNode }) {
  return (
    <pre className="overflow-x-auto rounded-md border border-border bg-canvas-inset p-4 text-xs leading-5">
      <code>{children}</code>
    </pre>
  );
}

function Bullet({ term, children }: { term: string; children: React.ReactNode }) {
  return (
    <li className="flex gap-2">
      <span aria-hidden className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
      <span>
        <strong className="text-fg">{term}</strong> — {children}
      </span>
    </li>
  );
}
