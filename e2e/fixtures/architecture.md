# System Architecture

## Overview

Mentor is a RAG (Retrieval-Augmented Generation) assistant that answers questions
about a team's code and documentation.

## Key Components

### Ingestion Pipeline

The ingestion pipeline processes documents through these stages:

1. **Parsing** — Extract text from PDF, DOCX, Markdown, or code files.
2. **Normalization** — Clean and normalize the extracted text.
3. **Chunking** — Split into semantic chunks of ~512 tokens with overlap.
4. **Embedding** — Convert each chunk to a 1536-dim vector.
5. **Indexing** — Store vectors in pgvector with HNSW index.

### Retrieval

Vector similarity search using pgvector cosine distance. Returns top-K chunks
ranked by relevance score. Confidence is assessed based on top similarity and
average similarity of the window.

### Chat Orchestration

The orchestrator coordinates retrieval, confidence assessment, context building,
and LLM streaming. It persists all messages with citations and metadata.

## Configuration

Key settings:
- `RETRIEVAL_TOP_K=8`: Number of chunks retrieved per query
- `RETRIEVAL_MIN_TOP_SIMILARITY=0.25`: Minimum top score threshold
- `CHAT_MAX_CONTEXT_CHUNKS=8`: Maximum chunks passed to LLM
