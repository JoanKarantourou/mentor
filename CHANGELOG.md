# Changelog

## Documentation pass — positioning and contributor docs

Rewrote `README.md` for three audiences (skimmer, deployer, contributor). Added `CONFIGURATION.md` (full settings reference), `DEPLOYMENT.md` (local, VPS, and cloud-managed recipes with production checklist), `ARCHITECTURE.md` (data flow diagrams, provider abstraction walkthrough, database schema, curation feature overview, testing guide), and `CONTRIBUTING.md`. Polished `.env.example` with grouped sections and one-line comments on every setting. Added GitHub issue and PR templates. Added `examples/sample-corpus/` with seven fixture files for a first-run demo, plus `examples/queries.md` with suggested queries. Added `*.log` to `.gitignore`.

## Stage 8 — Curation features

### Memory extraction

Conversations can be summarised into durable Markdown notes. The orchestrator checks for trigger conditions (conversation length, topic shift, session gap) after each assistant message and emits a `memory_suggestion` SSE event when they are met. Confirming in the UI calls `POST /curation/conversations/{id}/extract-memory`, which runs a structured LLM extraction and saves the result as a document with `source_type=memory`.

**Triggers:** `long_conversation` (>= `MEMORY_EXTRACTION_MIN_MESSAGES`), `topic_shift` (cosine similarity of adjacent message embeddings drops below threshold), `session_break` (gap between messages exceeds `MEMORY_EXTRACTION_SESSION_BREAK_MINUTES`).

### Duplicate detection

When a document reaches `indexed` status, its chunk embeddings are compared against all existing chunk embeddings. If more than `DUPLICATE_MATCH_RATIO` of the chunks exceed `DUPLICATE_NEAR_THRESHOLD` cosine similarity with another document's chunks, the document is flagged in `documents.duplicate_check` (JSONB). Configurable and disableable via env. Results surfaced in the documents list UI.

### Gap analysis

When the orchestrator takes the refusal path (path 4 — corpus insufficient, no web search), it calls `analyze_gap()` with the rejected query and the top retrieved chunks. The LLM returns a structured JSON response identifying the missing topic, related topics present, and suggested document types. Emitted as a `gap_analysis` SSE event and rendered in the low-confidence notice in the UI.

### Curation API

- `POST /curation/conversations/{id}/extract-memory` — extract and save memory note
- `GET /curation/documents/{id}/duplicate-check` — retrieve duplicate check result
- `POST /curation/documents/{id}/duplicate-check` — trigger duplicate check manually

## Stage 7 — Web search + test hardening

### Web search (opt-in per question)

Added an opt-in web search escape hatch. When the user toggles the 🌐 button for a specific message, Mentor performs a Tavily search, combines corpus and web context with visual separation, and streams an answer that cites both sources distinctly.

**Web search flow:**
- `WEB_SEARCH_PROVIDER=stub` (default) — deterministic fake results, no key needed
- `WEB_SEARCH_PROVIDER=tavily` — real results via Tavily (free tier: 1000/month, sign up at tavily.com)
- Web search is **off by default** and **opt-in per question** — never automatic, never sticky across messages
- Toggle resets to "off" after every send

**Backend:**
- `WebSearchProvider` ABC + `StubWebSearchProvider` + `TavilyWebSearchProvider`
- `TavilyWebSearchProvider` calls `api.tavily.com/search` directly with tenacity retry (3 attempts, retries on ConnectError, TimeoutException, and 429/5xx)
- `ChatTurnInput` extended with `enable_web_search: bool = False`
- Four orchestrator paths: corpus-only (confident), corpus+web (confident+search), web-only (insufficient+search), refusal (insufficient, no search)
- New SSE events: `web_search_started`, `web_search_results`; `sources` event extended with `web_sources` array
- `<cited_web>1,2</cited_web>` tag parsed alongside `<cited_chunks>`; citation parser extended to return both
- `messages` table extended with `web_search_used`, `web_search_results` (JSONB), `web_search_provider`
- Health endpoint checks web search provider (returns `"stub"` for stub, live probe for Tavily)

**Frontend:**
- Web search toggle pill in `MessageInput` — resets to off after each send
- "🌐 Searching the web..." → "🌐 Found N web results" streaming indicator
- Sources section split into corpus ("📁 From your documents") and web ("🌐 From the web") subsections
- `WebSourceCard` — shows favicon + domain + title + snippet + published date, links to URL in new tab
- `LowConfidenceNotice` gains optional "Try with web search" button
- "Not in your documents — searched the web instead" lighter notice when web fills the gap
- 🌐 badge on assistant messages that used web search

### Test hardening

**Backend tests** (target: 160+):
- `test_web_search_providers.py` — 15 new tests: stub determinism, Tavily HTTP mock, retry/exhaustion, factory
- `test_web_search_orchestrator.py` — 10 new tests: all 4 orchestrator paths, persistence, failure fallback, edge cases
- `test_chat_edge_cases.py` — 10 new tests: SSE events, conversation continuity, regenerate edge cases, DB persistence
- `test_ingestion_edge_cases.py` — 8 new tests: 0-byte file, size limit, deceptive extension, Greek text, concurrent uploads, nested headings, Haskell/Lua fallback
- `test_search_edge_cases.py` — 4 new tests: empty corpus, deleted docs, exact match self-consistency, filter zero matches
- 50 MB file size limit enforced in `POST /documents/upload` via `MAX_UPLOAD_SIZE_BYTES` config

**Frontend tests** (target: 35+):
- `test_chat.test.ts` — 4 new SSE parser tests: web search events, mixed order, abrupt stream end, empty stream
- `MessageSources.test.tsx` — 9 tests: empty, corpus-only, web-only, mixed, toggle
- `SourceCard.test.tsx` — 10 tests: corpus card (score %, click, truncation) + web card (link, favicon, date)
- `LowConfidenceNotice.test.tsx` — 4 new tests: try-with-web button, `WebSearchUsedNotice` component
- `MessageInput.test.tsx` — 7 tests: toggle reset on send, web search flag, model tier
- `Message.test.tsx` — 5 new tests: pending indicator, result count, web badge, "Try with web search" integration
- `documents.test.ts` — 3 new tests: network failure, 500 error

**E2E tests** (`e2e/`):
- `test_full_ingestion.py` — upload 3+ fixture docs (English + Greek), verify all reach `indexed`
- `test_chat_flows.py` — 4 scenarios: grounded answer, honesty (5 off-topic questions), web search opt-in, conversation continuity + delete
- `test_resilience.py` — health check, delete removes from search, nonsense query returns empty
- `e2e/conftest.py` — session-scoped docker compose fixture (skippable via `E2E_SKIP_COMPOSE=1`)
- `Makefile` — `make test` (backend + frontend), `RUN_E2E=1 make test` adds E2E
- `scripts/run-e2e.sh` — standalone E2E runner

## Stage 6 — Frontend chat UI

Added a full Next.js chat interface with streaming, source drawers, document management, and dark theme. Real-time message streaming via SSE, cited source previews with expandable drawers, model tier selection (Haiku/Sonnet), regenerate button, conversation list with titles, document upload with drag-and-drop, and status polling.

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
