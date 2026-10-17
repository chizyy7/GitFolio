# GitFolio

**A self-hosted, AI-powered version control and developer-portfolio platform.**

GitFolio gives you the GitHub-shaped features developers expect — profiles,
repositories, commits, diffs, contribution heatmaps and a developer directory —
then layers on a **completely local** AI that reads, reviews and explains your
code. Push a real Git commit and Llama 3.2 will review the diff, write the commit
message, embed the sources for semantic search and answer questions about your
own repository with clickable citations.

> No OpenAI. No Anthropic. No per-token bills. The intelligence layer runs on your
> hardware with models you can inspect and swap.

---

## ✨ Features

**Version control**
- Real Git commits (`pygit2`) with SHA-1 identity, parent and author — one bare
  object database per repository on disk.
- Push files from the browser or from the terminal with the bundled CLI.
- Browse the file tree, syntax-highlighted sources, commit history and unified
  diffs (green/red gutters, per-file stats).

**Local AI (Llama 3.2 via Ollama + ChromaDB)**
- **AI Repo Explainer** — RAG chat that retrieves the most relevant functions and
  classes and explains them, citing `file.py:42` pills that jump straight to the line.
- **AI Code Review** — every push is reviewed for bugs, security issues, style and
  suggestions, with severity tags, file and line numbers.
- **Semantic code search** — search by *intent*, not substring.
- **Auto-Commit Message Generator** — leave the message blank and the model writes
  a conventional-commit summary from the diff.
- **AI Skill Mapper** — profiles your stack into proficiency-tagged skill badges.

**Portfolio & insights**
- GitHub-style profiles with pinned repositories and AI skill badges.
- Contribution heatmap with streaks, weekly activity (Recharts area chart) and a
  language doughnut.
- Developer directory (`/explore`) with search.
- Dark-mode-first theme (plus a light mode), JWT-secured accounts.

---

## 🏗️ Architecture

```
┌──────────────────────────┐        ┌──────────────────────────────────┐
│  Next.js 14 (App Router) │  REST  │  FastAPI + SQLAlchemy            │
│  • server components     │ ─────▶ │  • JWT OAuth2 password bearer    │
│  • Recharts + heatmap    │        │  • /auth /repos /push /ai …      │
│  • Shiki via route handler│       │                                   │
└──────────────────────────┘        └───────┬────────────┬─────────────┘
                                            │            │
                       ┌────────────────────┘            └───────────────┐
                       ▼                                                  ▼
              ┌─────────────────┐   embeddings    ┌────────────────────────────┐
              │  PostgreSQL 16  │                 │  ChromaDB (per-repo vectors)│
              │  users repos    │                 └──────────────┬─────────────┘
              │  commits files  │                                │ retrieve
              │  reviews skills │                 ┌──────────────▼─────────────┐
              └─────────────────┘                 │  Ollama · Llama 3.2         │
                       ▲                          │  + nomic-embed-text         │
                       │  bare Git object stores  └────────────────────────────┘
                       └──  STORAGE_PATH/<user>/<repo>  (on-disk, via pygit2)
```

**Design notes**

- PostgreSQL is the authoritative store for file *content*; the Git object
  database provides commit identity and history.
- Unified diffs are generated deterministically (line numbers the AI reviewer can
  trust) rather than pulled from libgit2 patches.
- Every AI capability degrades gracefully: if Ollama/Chroma are down, pushes still
  succeed and the UI explains what to start.

---

## 🧰 Tech stack

| Layer      | Technology                                                                 |
| ---------- | -------------------------------------------------------------------------- |
| Frontend   | Next.js 14 (App Router), React 18, TypeScript, Tailwind CSS, Recharts, Lucide, Shiki, `react-calendar-heatmap` |
| Backend    | FastAPI, SQLAlchemy 2.0, Pydantic v2, PostgreSQL, JWT (python-jose), passlib |
| Version control | pygit2, `difflib` unified diffs                                      |
| AI         | Ollama (Llama 3.2 chat, nomic-embed-text embeddings), ChromaDB, tree-sitter chunking |
| Deployment | Docker, Docker Compose, Vercel (frontend), Render/Railway/AWS (backend)     |

---

## 📁 Repository layout

```
gitfolio/
├── backend/                     # FastAPI application
│   ├── app/
│   │   ├── api/routes/          # auth, repos, vcs (push), ai, profiles, dashboard, system
│   │   ├── core/                # config, security, logging
│   │   ├── db/                  # engine, session, declarative base
│   │   ├── models/              # User, Repository, Commit, File, AIReview, UserSkill
│   │   ├── schemas/             # Pydantic request/response DTOs
│   │   ├── services/            # vcs (pygit2), tree, language
│   │   │   └── ai/              # chunker, embeddings, ingestion, rag, reviewer, skills
│   │   ├── workers/tasks.py     # post-push pipeline
│   │   └── main.py              # app factory + lifespan
│   ├── scripts/init_db.py       # schema create + optional demo seed
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                    # Next.js application
│   ├── src/app/                 # routes: /, /login, /register, /dashboard,
│   │                            #   /explore, /docs, /[username], /[username]/[repo]…
│   ├── src/components/          # heatmap, charts, chat, diff, file tree, push panel…
│   ├── src/context/AuthContext  # JWT session state
│   ├── src/lib/                 # api client, types, utils, highlight
│   └── Dockerfile
├── cli/gitfolio.py              # dependency-free push/login/whoami CLI
├── docker-compose.yml           # postgres + chroma + ollama + backend + frontend
├── .env.example
├── DEPLOYMENT.md
└── README.md
```

---

## 🚀 Quick start

### Docker Compose (everything)

```bash
cp .env.example .env                          # then set JWT_SECRET
docker compose up --build                     # models pull automatically on first run

# optional demo account
docker compose exec backend python -m scripts.init_db --seed
```

- Frontend: <http://localhost:3000>
- API docs: <http://localhost:8000/docs>

### Local development

```bash
# --- backend ---
cd backend
python -m venv .venv && . .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example .env                          # adjust DATABASE_URL / JWT_SECRET
python -m scripts.init_db --seed
uvicorn app.main:app --reload --port 8000

# --- frontend ---
cd ../frontend
npm install
cp .env.local.example .env.local
npm run dev
```

You will also need **PostgreSQL**, **Ollama** (`ollama serve` +
`ollama pull llama3.2 && ollama pull nomic-embed-text`) and **ChromaDB**
(`docker run -p 8001:8000 ghcr.io/chroma-core/chroma:0.5.23` — then set
`CHROMA_PORT=8001` in `backend/.env`, since port 8000 is taken by the API
itself). The backend boots without them; only the AI features are disabled.

---

## ⌨️ CLI

Push a local directory as a single commit — no `git` required, standard library
only.

```bash
# authenticate (prints a token)
python cli/gitfolio.py login --username octocat --password secret

# push
python cli/gitfolio.py push ./my-project \
  --api http://localhost:8000/api \
  --token "$GITFOLIO_TOKEN" \
  --repo <repository-id> \
  --message "feat: initial import"
```

Useful flags: `--delete PATH` (repeatable), `--ignore NAME` (repeatable),
`--no-ai`, `--dry-run`, `--branch`.

---

## 🔌 API overview

Everything is under `/api`. Authenticated routes take
`Authorization: Bearer <token>`. The generated OpenAPI schema is at `/docs`.

| Method | Path                              | Purpose                                |
| ------ | --------------------------------- | -------------------------------------- |
| POST   | `/auth/register`                  | Create an account, receive a JWT        |
| POST   | `/auth/login`                     | OAuth2 password flow                    |
| GET    | `/auth/me`                        | Current user                            |
| GET    | `/users`                          | Developer directory (searchable)        |
| GET    | `/users/{username}`               | Public profile + skills + stats         |
| GET    | `/repos/{username}`               | List a user's repositories              |
| POST   | `/repos`                          | Create a repository                     |
| GET    | `/repos/{username}/{repo}`        | Detail + file tree                      |
| GET    | `/repos/{username}/{repo}/blob`   | One file's content                      |
| POST   | `/repos/{id}/push`                | Push files, create a commit             |
| GET    | `/repos/{id}/commits`             | Commit history                          |
| GET    | `/repos/{id}/commits/{hash}`      | Commit diff + AI review                 |
| POST   | `/ai/chat`                        | RAG chat over the repository            |
| POST   | `/ai/search`                      | Semantic code search                    |
| GET    | `/ai/reviews/{commit}`            | AI review for a commit                  |
| POST   | `/ai/index/{repo}`                | Embed a repository                      |
| POST   | `/ai/skills/refresh`              | Re-run the skill mapper                 |
| GET    | `/dashboard/{username}`           | Heatmap, activity, languages, pinned    |

---

## 🧠 How the AI works

1. **Chunk** — changed files are split along AST boundaries with tree-sitter
   (falling back to line windows) so functions and classes stay whole.
2. **Embed** — chunks are embedded with `nomic-embed-text` and upserted into a
   per-repository ChromaDB collection.
3. **Retrieve** — a question is embedded and the top-K chunks are fetched.
4. **Generate** — Llama 3.2 answers using only the retrieved context and returns
   citations that map back to exact file/line ranges.

Reviews, commit messages and skill profiles follow the same pattern: a focused
prompt, strict output parsing, and a heuristic fallback if the model is offline.

---

## 🔐 Security & privacy

- JWT access tokens (HS256), bcrypt-hashed passwords.
- Private repositories are scoped to their owner and reported as `404` to others.
- Pushed file paths are validated against traversal; sizes and counts are capped.
- Your code, embeddings and model prompts never leave your infrastructure.

---

## 📦 Deployment

See **[DEPLOYMENT.md](./DEPLOYMENT.md)** for step-by-step guides: Vercel for the
frontend, Render/Railway/AWS for the backend, managed PostgreSQL, and hosting
Ollama + ChromaDB.

---

## 📄 License

MIT.
