# AGENTS.md

GitFolio: self-hosted AI-powered version-control + developer portfolio. Three
independent pieces — `backend/` (FastAPI), `frontend/` (Next.js 14 App Router),
`cli/` (stdlib-only Python client). No monorepo tooling, no shared package; each
side is built and run on its own.

Full architecture and API tables live in `README.md`; deployment in
`DEPLOYMENT.md`. This file only covers what those don't make obvious.

## Commands

Backend (run **from `backend/`**, imports are `app.*`):
```bash
python -m venv .venv && . .venv/Scripts/activate   # Windows; bash: .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env          # backend reads backend/.env and ../.env
python -m scripts.init_db --seed # schema + demo user (demo / demo-password-123)
uvicorn app.main:app --reload --port 8000
```

Frontend (run from `frontend/`, Node >= 18.18):
```bash
npm install
cp .env.local.example .env.local
npm run dev
npm run lint       # next lint
npm run typecheck  # tsc --noEmit
npm run build
```

Whole stack: `cp .env.example .env` then `docker compose up --build`. The
`ollama-init` service pulls `llama3.2` + `nomic-embed-text` once (multi-GB, slow
first boot).

- **No test suite exists.** `pytest`/`pytest-asyncio` are in
  `backend/requirements.txt` and `db/session.py` mentions a SQLite test path, but
  there are no `test_*.py` files and no pytest config. Don't claim to run tests;
  verification is `typecheck` + `lint` (frontend) and a manual boot (backend).
- **No Alembic despite the tooling.** `alembic` is a dependency, but there is no
  `alembic/` directory or `alembic.ini`. Schema is created either by
  `AUTO_CREATE_TABLES=true` on boot or `python -m scripts.init_db`; the docs no
  longer tell you to run `alembic upgrade head`.
- No CI, no pre-commit, no root manifest or Makefile. No backend linter/formatter
  config in the repo.

## Backend conventions (`backend/app/`)

- **All env access goes through `app/core/config.py`** (a cached `settings`
  singleton). Never read `os.environ` elsewhere — the module docstring states this
  as a rule. Add new tunables as `Settings` fields + document in `.env.example`.
- Request flow: `main.create_app()` → `api/routes/__init__.api_router`
  (`/api` prefix) → `api/deps.py` for auth/session/repo lookups. Add shared
  auth/lookup logic in `deps.py`, not per-route.
- `api/deps.py` `can_view`/`get_repo_or_404` deliberately return **404 for
  private repos** the viewer can't see (GitHub behavior). Don't "fix" this to 403.
- Postgres is authoritative for file *content*; the on-disk pygit2 object store
  under `STORAGE_PATH` holds only commit identity/history. Uncommitted content
  lives in the `files` table.
- Diffs are generated deterministically with `difflib` (see `services/vcs.py`),
  not libgit2 patches, because the AI reviewer depends on exact line numbers.
  Don't swap this out.
- Push pipeline (`api/routes/vcs.py` `push`): load state → diff → generate commit
  message (Ollama with fallback) → write commit → queue
  `workers.tasks.post_push_pipeline` (index → review → skills). Each AI stage is
  isolated and must degrade gracefully when Ollama/Chroma are down.
- The app must boot with **no** Postgres/Ollama/Chroma running (only AI features
  disable). Preserve this when touching startup/`lifespan`.

## Frontend conventions (`frontend/src/`)

- All backend calls go through the typed client in `src/lib/api.ts` (auth token
  from `localStorage` key `gitfolio.token`). Add endpoints there and to
  `src/lib/types.ts`.
- `NEXT_PUBLIC_API_URL` (must include `/api`) is **inlined at build time** —
  changing it requires a rebuild/redeploy, not just a restart.
- Shiki highlighting runs server-side via the route handler
  `src/app/api/highlight/route.ts`, not in client components.
- App routes use `[username]/[repoName]` params and `RequireAuth` for gated pages.

## CLI (`cli/gitfolio.py`)

Keep it **standard library only** — no backend dependencies. It talks to the
running API over HTTP (`GITFOLIO_API` / `GITFOLIO_TOKEN` env defaults).

## Environment

The backend reads both `backend/.env` and the repo-root `../.env` when run
locally, so a root `.env` affects backend runs too. `DATABASE_URL` must use the
`+psycopg` driver. `JWT_SECRET` has a dev default that must be changed in
production. `STORAGE_PATH` must be a persistent volume or repositories vanish on
redeploy.
