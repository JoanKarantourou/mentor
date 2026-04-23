# Changelog

## Stage 4 — Azure OpenAI embeddings

Added `AzureOpenAIEmbeddingProvider` with exponential-backoff retry logic, stale vector detection, a `/admin/reindex` endpoint to re-embed documents that were indexed with the stub provider, and live health checks that surface credential errors immediately on startup. The stub provider remains the default; Azure OpenAI is opt-in via `EMBEDDING_PROVIDER=azure_openai`.

## Stage 3 — Chunking, embeddings, vector search

Added markdown-aware and code-aware chunking with configurable target and overlap token counts. Chunks are stored as 1536-dimensional vectors in PostgreSQL via pgvector, with an HNSW index for fast approximate nearest-neighbor search. Added a similarity search endpoint that returns ranked results with source metadata.

## Stage 2 — Ingestion pipeline

File upload endpoint with background task processing. Documents are parsed via `unstructured`, language-detected (English and Greek), and normalized to Markdown before storage. Soft-delete support and a status polling endpoint included.

## Stage 1 — Project skeleton

Initial project structure: FastAPI backend with SQLModel and Alembic migrations, PostgreSQL 16 + pgvector via Docker Compose, Next.js 14 frontend placeholder, and a provider abstraction layer for LLM and embedding backends with stub implementations.
