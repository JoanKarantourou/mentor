# mentor

An internal RAG assistant for small teams. Built with FastAPI, Next.js, PostgreSQL + pgvector, and a clean provider abstraction for LLM and embedding backends.

## Setup

```bash
cp .env.example .env
docker compose up
```

- Backend API + docs: http://localhost:8000/docs
- Frontend: http://localhost:3000
- Health check: http://localhost:8000/health

## Stack

- **Backend:** Python 3.12, FastAPI, SQLModel, Alembic, PostgreSQL 16 + pgvector
- **Frontend:** Next.js 14, TypeScript, Tailwind CSS, shadcn/ui
- **Infrastructure:** Docker Compose (local), Azure Container Apps (production target)
