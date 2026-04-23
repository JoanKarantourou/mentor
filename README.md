# Mentor

*A self-hosted RAG assistant for small teams and personal use.*

Mentor indexes your code and documentation and answers questions with honest source citations. It's open-source, self-hostable via Docker Compose, and designed to be straightforward to run without cloud dependencies.

## Status

| Area | State |
|------|-------|
| Ingestion pipeline (upload, parse, normalize) | Done |
| Markdown-aware + code-aware chunking | Done |
| Vector storage with pgvector (HNSW index) | Done |
| Stub embedding provider (dev default) | Done |
| Azure OpenAI embedding provider | Done |
| Direct OpenAI embedding provider | Planned (Stage 5) |
| LLM chat interface | Planned (Stage 5) |
| Authentication | Deferred |
| Frontend UI | Placeholder only |

## Quick start

```bash
cp .env.example .env
docker compose up
```

No credentials required — the default configuration uses the stub embedding provider, which is sufficient for development and testing.

- Backend API + docs: http://localhost:8000/docs
- Frontend: http://localhost:3000
- Health check: http://localhost:8000/health

## Architecture

```
┌─────────────┐     ┌─────────────────────────────────┐
│  Next.js    │────▶│  FastAPI backend                 │
│  frontend   │     │  ├── ingestion pipeline           │
└─────────────┘     │  ├── chunking + embedding         │
                    │  └── similarity search (pgvector) │
                    └──────────────┬──────────────────┘
                                   │
                    ┌──────────────▼──────────────────┐
                    │  PostgreSQL 16 + pgvector        │
                    └─────────────────────────────────┘
```

- **Backend:** Python 3.12, FastAPI, SQLModel, Alembic
- **Database:** PostgreSQL 16 + pgvector (HNSW index, 1536-dim vectors)
- **Frontend:** Next.js 14, TypeScript, Tailwind CSS, shadcn/ui (placeholder)
- **Infrastructure:** Docker Compose (local dev), provider-agnostic LLM and embedding interfaces

## Providers

Mentor uses a provider abstraction for both LLM and embedding backends. You can swap providers via environment variable with no code changes.

### Embeddings

| Provider | Status | Notes |
|----------|--------|-------|
| `stub` | **Default** | Returns deterministic random vectors — good for dev, meaningless similarity |
| `azure_openai` | Implemented | Requires Azure credentials (see below) |
| `openai` | Planned | Direct OpenAI API — coming in Stage 5 |

### LLM

| Provider | Status | Notes |
|----------|--------|-------|
| `stub` | **Default** | Returns placeholder responses |
| `anthropic` | Planned | Direct Anthropic API — coming in Stage 5 |

## Switching to Azure OpenAI embeddings

The default `EMBEDDING_PROVIDER=stub` returns random vectors useful for development but produces meaningless similarity results. To enable real semantic search via Azure OpenAI:

### 1. Provision Azure OpenAI

1. Create an Azure OpenAI resource in the Azure portal.
2. Under **Model deployments**, create a deployment using model `text-embedding-3-small`. Note the deployment name.
3. Go to **Keys and Endpoint** and copy the endpoint URL and one of the API keys.

### 2. Configure the backend

Uncomment and fill in the Azure section of your `.env`:

```env
EMBEDDING_PROVIDER=azure_openai
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_API_KEY=your-key-here
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-small
AZURE_OPENAI_API_VERSION=2024-02-01
```

### 3. Restart and verify

```bash
docker compose up --build
curl http://localhost:8000/health
```

A healthy response includes `"embedding_provider": "ok"`. Credential errors appear immediately — no silent failures.

### 4. Re-embed existing documents

Documents indexed with the stub provider have meaningless vectors. Re-embed only those:

```bash
curl -X POST http://localhost:8000/admin/reindex \
  -H "Content-Type: application/json" \
  -d '{"only_stale": true}'
```

Returns `{"reindexed": N}` immediately (202 Accepted).

### 5. Monitor progress

```bash
watch -n 2 'curl -s http://localhost:8000/admin/embeddings/status | python3 -m json.tool'
```

When `stale_chunks` reaches `0`, all documents are backed by real vectors and semantic search is active.

## Roadmap

- [x] **Stage 1** — Project skeleton: FastAPI + Postgres + pgvector + Docker Compose + Next.js placeholder
- [x] **Stage 2** — Ingestion pipeline: file upload, parsing, language detection, Markdown normalization
- [x] **Stage 3** — Chunking + vector search: markdown/code-aware chunking, 1536-dim storage, similarity search
- [x] **Stage 4** — Real embeddings: Azure OpenAI provider with retry, stale detection, health checks, reindex endpoint
- [ ] **Stage 5** — LLM chat: direct Anthropic + OpenAI providers, retrieval-augmented generation, streaming
- [ ] **Stage 6** — Frontend: chat UI, document browser, source citation display
- [ ] **Stage 7** — Auth: deferred until the core product is solid

## License

MIT — see [LICENSE](LICENSE).
