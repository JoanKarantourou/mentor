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
| Direct OpenAI embedding provider | Done |
| LLM chat with grounding and streaming | Done |
| Anthropic direct API (Claude) | Done |
| Conversation history | Done |
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
                    │  ├── similarity search (pgvector) │
                    │  └── chat orchestrator + LLM      │
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
| `openai` | **Recommended** | Direct OpenAI API — one API key, no cloud infra needed |
| `azure_openai` | Supported | For enterprise/Azure tenants — needs a resource + deployment |

### LLM

| Provider | Status | Notes |
|----------|--------|-------|
| `stub` | **Default** | Returns placeholder responses — no API key needed |
| `anthropic` | **Recommended** | Direct Anthropic API — Claude Haiku (default) + Sonnet (strong tier) |

## Switching to real embeddings

The default `EMBEDDING_PROVIDER=stub` returns random vectors useful for development but produces meaningless similarity results.

### Option A — OpenAI direct API (recommended for personal use)

One API key, no cloud infra, no resource provisioning.

**1.** Get an API key at [platform.openai.com → API Keys](https://platform.openai.com/api-keys).

**2.** Add to your `.env`:

```env
EMBEDDING_PROVIDER=openai
OPENAI_API_KEY=sk-...
```

**3.** Restart and re-embed existing documents:

```bash
docker compose up --build
curl -X POST http://localhost:8000/admin/reindex \
  -H "Content-Type: application/json" \
  -d '{"only_stale": true}'
```

A healthy `/health` response shows `"embedding_provider": "ok"`. Missing or invalid keys surface immediately — no silent failures.

### Option B — Azure OpenAI (enterprise / Azure tenant)

For teams already running on Azure. Requires more setup but keeps data within your Azure subscription.

**1.** Create an Azure OpenAI resource, provision a `text-embedding-3-small` deployment, and copy the endpoint + key.

**2.** Add to your `.env`:

```env
EMBEDDING_PROVIDER=azure_openai
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_API_KEY=your-key-here
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-small
AZURE_OPENAI_API_VERSION=2024-02-01
```

**3.** Restart and re-embed the same way as above.

## Chatting with Mentor

Mentor answers questions grounded in your indexed documents. It refuses to answer from general knowledge — if the corpus doesn't contain relevant information, it says so.

### Enable Claude (Anthropic)

Add to your `.env`:

```env
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
```

The default `claude-haiku-4-5` model handles most queries. A "strong" tier (Sonnet) is used for regenerations.

### Ask a question (streaming SSE)

```bash
curl -N -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "How does the ingestion pipeline process files?"}'
```

Each response is a stream of SSE events:

| Event | Payload |
|-------|---------|
| `retrieval` | chunk IDs retrieved + similarity scores |
| `confidence` | `{"sufficient": true/false, "reason": "..."}` |
| `token` | one streamed text fragment |
| `sources` | chunks cited in the response |
| `message_persisted` | `{"conversation_id": "...", "assistant_message_id": "..."}` |
| `done` | empty — stream complete |

When confidence is insufficient, Mentor responds with a canned "I don't have enough in the indexed documents" message rather than hallucinating.

### Continue a conversation

```bash
curl -N -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What about chunking?", "conversation_id": "..."}'
```

Pass `conversation_id` (from any `message_persisted` event) to continue in the same thread. Conversation history is stored in PostgreSQL.

### Conversation management

```bash
# List all conversations
curl http://localhost:8000/conversations

# Get full conversation with messages
curl http://localhost:8000/conversations/{id}

# Delete a conversation (cascades to messages)
curl -X DELETE http://localhost:8000/conversations/{id}
```

### Monitoring reindex progress

```bash
watch -n 2 'curl -s http://localhost:8000/admin/embeddings/status | python3 -m json.tool'
```

When `stale_chunks` reaches `0`, all documents are backed by real vectors and semantic search is active.

## Roadmap

- [x] **Stage 1** — Project skeleton: FastAPI + Postgres + pgvector + Docker Compose + Next.js placeholder
- [x] **Stage 2** — Ingestion pipeline: file upload, parsing, language detection, Markdown normalization
- [x] **Stage 3** — Chunking + vector search: markdown/code-aware chunking, 1536-dim storage, similarity search
- [x] **Stage 4** — Real embeddings: OpenAI direct + Azure OpenAI providers, retry, stale detection, health checks, reindex endpoint
- [x] **Stage 5** — LLM chat: Anthropic provider, grounded RAG with confidence gating, SSE streaming, citation extraction, conversation history
- [ ] **Stage 6** — Frontend: chat UI, document browser, source citation display
- [ ] **Stage 7** — Auth: deferred until the core product is solid

## License

MIT — see [LICENSE](LICENSE).
