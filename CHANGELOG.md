# Changelog

## Stage 5 — LLM chat and generation

Added full retrieval-augmented generation with grounding as a hard constraint. Mentor retrieves relevant chunks, assesses confidence via top and average similarity thresholds, and either streams a grounded answer from Claude or returns an honest refusal — never from general knowledge.

**LLM provider:** `AnthropicLLMProvider` using `AsyncAnthropic` directly. Supports streaming via `client.messages.stream`, with tenacity retry on 429s (respects `Retry-After` header) and connection errors. Two model tiers: `default` (Haiku) and `strong` (Sonnet, used for regenerations). `LLM_PROVIDER=stub` remains the zero-key default.

**Chat orchestrator:** Pure async generator (`run_chat_turn`) that yields typed events: `RetrievalEvent`, `ConfidenceEvent`, `TokenEvent`, `SourcesEvent`, `MessagePersistedEvent`, `DoneEvent`. Confidence gating uses both top similarity and average similarity of the top-N window. Citation extraction parses a `<cited_chunks>` tag the LLM is instructed to emit.

**API endpoints:**
- `POST /chat` — streams SSE; accepts optional `conversation_id` to continue a thread
- `POST /chat/{message_id}/regenerate` — re-runs with strong model tier, replaces the prior assistant message
- `GET /conversations` — lists conversations with message count
- `GET /conversations/{id}` — full thread with ordered messages
- `DELETE /conversations/{id}` — hard delete with cascade

**Database:** Two new tables (`conversations`, `messages`) via Alembic migration. Messages store retrieved and cited chunk IDs as JSONB, confidence flag, and token counts. Conversation title generated asynchronously from the first user message.

**Health check:** `/health` now probes the LLM provider with a short generation call; returns `"stub"` for the stub provider.

## Stage 4.1 — Direct OpenAI embeddings

Added `OpenAIEmbeddingProvider` as a simpler alternative to the Azure path. Uses the direct OpenAI API (`AsyncOpenAI`) with the same tenacity retry, tiktoken truncation, ordering assertion, and per-call logging as the Azure provider. Recommended for personal use — one API key, no cloud infra. `EMBEDDING_PROVIDER=openai` is now the suggested real-embedding option in the README and `.env.example`. Azure remains fully supported.

## Stage 4 — Azure OpenAI embeddings

Added `AzureOpenAIEmbeddingProvider` with exponential-backoff retry logic, stale vector detection, a `/admin/reindex` endpoint to re-embed documents that were indexed with the stub provider, and live health checks that surface credential errors immediately on startup. The stub provider remains the default; Azure OpenAI is opt-in via `EMBEDDING_PROVIDER=azure_openai`.

## Stage 3 — Chunking, embeddings, vector search

Added markdown-aware and code-aware chunking with configurable target and overlap token counts. Chunks are stored as 1536-dimensional vectors in PostgreSQL via pgvector, with an HNSW index for fast approximate nearest-neighbor search. Added a similarity search endpoint that returns ranked results with source metadata.

## Stage 2 — Ingestion pipeline

File upload endpoint with background task processing. Documents are parsed via `unstructured`, language-detected (English and Greek), and normalized to Markdown before storage. Soft-delete support and a status polling endpoint included.

## Stage 1 — Project skeleton

Initial project structure: FastAPI backend with SQLModel and Alembic migrations, PostgreSQL 16 + pgvector via Docker Compose, Next.js 14 frontend placeholder, and a provider abstraction layer for LLM and embedding backends with stub implementations.
