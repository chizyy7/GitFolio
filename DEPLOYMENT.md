# Deploying GitFolio

GitFolio has two deployable apps and three backing services:

| Component  | Technology            | Hosted on (examples)               |
| ---------- | --------------------- | ---------------------------------- |
| `frontend` | Next.js 14            | Vercel                             |
| `backend`  | FastAPI (Docker)      | Render / Railway / AWS ECS or EC2  |
| database   | PostgreSQL 16         | Render / Neon / RDS                |
| vectors    | ChromaDB              | Render / Railway / a sidecar       |
| LLM        | Ollama (Llama 3.2)    | GPU host / a box on your network   |

The AI services are optional. With `AI_ENABLED=false` the app still works as a
plain version-control + portfolio product; every AI call degrades gracefully.

---

## 1. Local (Docker Compose)

The entire stack — database, vector store, model server and both apps — comes up
with one command.

```bash
cp .env.example .env
# Set JWT_SECRET to a long random value:
python -c "import secrets; print(secrets.token_urlsafe(64))"

docker compose up --build
```

| Service    | URL                             |
| ---------- | ------------------------------- |
| Frontend   | <http://localhost:3000>         |
| API + docs | <http://localhost:8000/docs>    |
| ChromaDB   | <http://localhost:8001>         |
| Ollama     | <http://localhost:11434>        |

The `ollama-init` container pulls `llama3.2` and `nomic-embed-text` on first
run (a few GB — give it time). Seed a demo account:

```bash
docker compose exec backend python -m scripts.init_db --seed
# demo / demo-password-123
```

> **Note** — `NEXT_PUBLIC_API_URL` is compiled into the browser bundle. For
> Compose it defaults to `http://localhost:8000/api`, which is correct because
> the browser talks to the host-published backend port.

---

## 2. Frontend → Vercel

1. Push the repository to GitHub.
2. **New Project → Import**, then set **Root Directory** to `frontend`.
3. Framework preset is detected as **Next.js** (`frontend/vercel.json` supplies
   headers and the install/build commands).
4. Add an environment variable for **all** environments:

   | Name                   | Value                                  |
   | ---------------------- | -------------------------------------- |
   | `NEXT_PUBLIC_API_URL`  | `https://<your-backend>/api`           |
   | `NEXT_PUBLIC_SITE_NAME`| `GitFolio` (optional)                  |

5. Deploy. Because `NEXT_PUBLIC_*` values are inlined at build time, changing
   the API URL requires a redeploy.

---

## 3. Backend → Render

Render can build the backend straight from `backend/Dockerfile`.

1. **New → Web Service → Build from a Dockerfile.**
   - Root directory: `backend`
   - Dockerfile path: `backend/Dockerfile`
   - Health check path: `/api/health`
2. Add a **PostgreSQL** instance from the Render dashboard and copy its internal
   connection string.
3. Set the environment variables:

   | Key                      | Value                                                        |
   | ------------------------ | ------------------------------------------------------------ |
   | `DATABASE_URL`           | `postgresql+psycopg://…` (add the `+psycopg` driver to the URI) |
   | `JWT_SECRET`             | a long random string                                         |
   | `BACKEND_CORS_ORIGINS`   | `https://<your-vercel-app>.vercel.app`                       |
   | `ENVIRONMENT`            | `production`                                                 |
   | `DEBUG`                  | `false`                                                      |
   | `AUTO_CREATE_TABLES`     | `true` (first boot) then `false`                             |
   | `OLLAMA_HOST`            | `https://<your-ollama-host>`                                 |
   | `CHROMA_HOST` / `CHROMA_PORT` | your ChromaDB host / port                               |

4. **Persistent disk** — the bare Git object stores live on disk. Mount a Render
   disk at `/data` and keep `STORAGE_PATH=/data/repos`, otherwise every deploy
   wipes the repositories.
5. Deploy, then create the schema once:

   ```bash
   # Render Shell
   python -m scripts.init_db
   ```

### Railway

Same idea: deploy `backend/` from its Dockerfile, add the PostgreSQL and (if
used) ChromaDB plugins, and set the same variables. Attach a volume for
`/data/repos`.

---

## 4. Backend → AWS

**Option A — ECS Fargate**

- Build and push the image to ECR:

  ```bash
  aws ecr create-repository --repository-name gitfolio-backend
  docker build -t gitfolio-backend ./backend
  docker tag gitfolio-backend:latest <acct>.dkr.ecr.<region>.amazonaws.com/gitfolio-backend:latest
  aws ecr get-login-password | docker login --username AWS --password-stdin <acct>.dkr.ecr.<region>.amazonaws.com
  docker push <acct>.dkr.ecr.<region>.amazonaws.com/gitfolio-backend:latest
  ```

- Use **RDS for PostgreSQL** for `DATABASE_URL`.
- Mount an **EFS** volume at `/data/repos` so Git storage survives task restarts.
- Put the service behind an **ALB** with a `/api/health` target-group health check.
- Store `JWT_SECRET` and `DATABASE_URL` in **Secrets Manager** and inject them as
  container secrets.

**Option B — EC2 (single box)**

```bash
sudo apt-get update && sudo apt-get install -y docker.io docker-compose-plugin
git clone <your-repo> gitfolio && cd gitfolio
cp .env.example .env    # set JWT_SECRET, ENVIRONMENT=production, DEBUG=false
docker compose up -d --build
```

Front the box with nginx/Caddy for TLS; restrict ports 5432/8000/11434 to
localhost or the private subnet.

---

## 5. Hosting Ollama & ChromaDB

These are the only resource-hungry pieces.

- **Ollama** — ideally a GPU host. Run `Ollama/ollama`, expose 11434 (or put it
  behind an authenticated reverse proxy) and pull the models once:
  `ollama pull llama3.2 && ollama pull nomic-embed-text`.
- **ChromaDB** — run `ghcr.io/chroma-core/chroma:0.5.23` as its own service with a
  persistent volume. Mount it on `/chroma/chroma`. If you enable
  `CHROMA_AUTH_TOKEN`, match it in the backend.

If you would rather not host them, point `OLLAMA_HOST` at any OpenAI-compatible
Ollama endpoint and `CHROMA_HOST` at a managed Chroma instance. No application
code changes are required.

---

## 6. Configuration reference

All settings are read from environment variables (see `.env.example` and
`backend/app/core/config.py`).

| Variable                 | Default                     | Notes                                             |
| ------------------------ | --------------------------- | ------------------------------------------------- |
| `DATABASE_URL`           | local Postgres              | Must use the `+psycopg` driver.                   |
| `JWT_SECRET`             | dev value                   | **Change in production.**                         |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `10080`                | One week.                                         |
| `BACKEND_CORS_ORIGINS`   | localhost:3000              | Comma-separated allowed browser origins.          |
| `OLLAMA_HOST`            | `http://localhost:11434`    | Chat + embedding server.                          |
| `OLLAMA_CHAT_MODEL`      | `llama3.2`                  |                                                   |
| `OLLAMA_EMBED_MODEL`     | `nomic-embed-text`          |                                                   |
| `CHROMA_HOST`/`PORT`     | `localhost` / `8000`        | Vector store.                                     |
| `STORAGE_PATH`           | `/data/repos`               | **Must be a persistent volume.**                  |
| `AI_ENABLED`             | `true`                      | Set `false` for a pure VCS deployment.            |
| `ENABLE_BACKGROUND_AI`   | `true`                      | Enables post-push review/embedding.               |
| `AUTO_CREATE_TABLES`     | `true`                      | Schema is created from the ORM metadata on boot (Alembic is not bundled). |
| `NEXT_PUBLIC_API_URL`    | `http://localhost:8000/api` | Frontend → backend, **build-time**.               |

---

## 7. Production checklist

- [ ] `JWT_SECRET` is a long, random, unique value.
- [ ] `ENVIRONMENT=production`, `DEBUG=false`.
- [ ] `BACKEND_CORS_ORIGINS` lists only your real frontend origins.
- [ ] `AUTO_CREATE_TABLES` left `true` (Alembic migrations are not bundled yet).
- [ ] A persistent volume is mounted at `STORAGE_PATH`.
- [ ] PostgreSQL backups are enabled.
- [ ] TLS terminates in front of both apps.
- [ ] Ollama/ChromaDB are not publicly exposed without auth.
- [ ] Health checks point at `/api/health` (liveness) and `/api/health/ready`.

---

## 8. Troubleshooting

| Symptom                                   | Likely cause / fix                                                        |
| ----------------------------------------- | ------------------------------------------------------------------------- |
| `Cannot reach the GitFolio API` in the UI | `NEXT_PUBLIC_API_URL` wrong, or the backend is down. Redeploy after fixing. |
| CORS errors in the browser console        | Add the frontend origin to `BACKEND_CORS_ORIGINS` and restart the backend. |
| AI review stuck on `pending`              | Ollama is unreachable or the model is not pulled. Check `/api/ai/health`.  |
| `Repository not found` after a redeploy   | `STORAGE_PATH` was not a persistent volume; the Git stores were lost.      |
| Chat says the repo is "not been indexed"  | Build the index from the repo's AI tab (`POST /api/ai/index/{repo_id}`).   |
| Database errors on boot                   | Postgres not ready or `DATABASE_URL` missing the `+psycopg` driver.        |
