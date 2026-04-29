# Configuration

All settings are read from environment variables (or a `.env` file at startup). Copy `.env.example` to `.env` and edit as needed.

Settings with a `*` in the Required column are mandatory when the corresponding provider is selected; all others have defaults.

---

## Provider selection

| Variable | Default | Options | Description |
|----------|---------|---------|-------------|
| `LLM_PROVIDER` | `stub` | `stub`, `anthropic` | Which LLM backend to use for chat generation. |
| `EMBEDDING_PROVIDER` | `stub` | `stub`, `openai`, `azure_openai` | Which embedding backend to use for indexing and retrieval. |
| `WEB_SEARCH_PROVIDER` | `stub` | `stub`, `tavily` | Which web search backend to use. Web search is opt-in per question. |

---

## Anthropic (LLM)

Required when `LLM_PROVIDER=anthropic`.

Get an API key at [console.anthropic.com](https://console.anthropic.com).

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` * | — | API key. |
| `ANTHROPIC_DEFAULT_MODEL` | `claude-haiku-4-5` | Model used for standard queries. Haiku is fast and inexpensive. |
| `ANTHROPIC_STRONG_MODEL` | `claude-sonnet-4-5` | Model used when the user selects the "strong" tier (regenerate button). |

---

## OpenAI embeddings

Required when `EMBEDDING_PROVIDER=openai`. Recommended for personal use — one key, no cloud infrastructure.

Get an API key at [platform.openai.com/api-keys](https://platform.openai.com/api-keys).

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` * | — | API key. |
| `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding model. Must produce 1536-dimensional vectors. Do not change unless you also change the pgvector column dimension and reindex. |

---

## Azure OpenAI embeddings

Required when `EMBEDDING_PROVIDER=azure_openai`. For teams already running on Azure who want data to stay within their Azure subscription.

All three marked required fields must be set.

| Variable | Default | Description |
|----------|---------|-------------|
| `AZURE_OPENAI_ENDPOINT` * | — | Your Azure OpenAI resource endpoint. Azure portal → your resource → Keys and Endpoint → Endpoint. Example: `https://my-resource.openai.azure.com`. |
| `AZURE_OPENAI_API_KEY` * | — | Azure portal → your resource → Keys and Endpoint → KEY 1 or KEY 2. |
| `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` * | — | The deployment name you chose when creating the `text-embedding-3-small` deployment in Azure. This is the deployment name, not the model name. |
| `AZURE_OPENAI_API_VERSION` | `2024-02-01` | API version. Update only when Microsoft deprecates the current version. |

---

## Web search (Tavily)

Required when `WEB_SEARCH_PROVIDER=tavily`.

Sign up for a free API key at [tavily.com](https://tavily.com). Free tier: 1000 searches/month.

| Variable | Default | Description |
|----------|---------|-------------|
| `TAVILY_API_KEY` * | — | API key. |
| `TAVILY_SEARCH_DEPTH` | `basic` | `basic` (faster, cheaper) or `advanced` (more comprehensive, higher cost). |
| `WEB_SEARCH_MAX_RESULTS` | `5` | Maximum number of web results returned per query and passed to the LLM context. |

---

## Database

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+psycopg://postgres:postgres@db:5432/mentor` | Full PostgreSQL connection URL. Change the host when not using Docker Compose's `db` service. |
| `POSTGRES_USER` | `postgres` | PostgreSQL superuser name. Used by the Docker Compose `db` service to initialise the database. |
| `POSTGRES_PASSWORD` | `postgres` | PostgreSQL superuser password. **Change this for any non-local deployment.** |
| `POSTGRES_DB` | `mentor` | Database name. |

---

## Storage

| Variable | Default | Description |
|----------|---------|-------------|
| `BLOB_STORE` | `local` | Blob storage backend. Only `local` is implemented. Uploaded files are stored on the container filesystem. |
| `BLOB_STORE_ROOT` | `/data/blobs` | Root directory for local blob storage, inside the backend container. Corresponds to the `backend_data` Docker volume. |

---

## Retrieval tuning

These thresholds control the confidence gate — when Mentor decides it knows enough to answer versus when it refuses. The defaults work well for most corpora; adjust if you see too many false refusals (lower thresholds) or too many unsupported answers (raise thresholds).

| Variable | Default | Description |
|----------|---------|-------------|
| `RETRIEVAL_TOP_K` | `8` | Number of chunks retrieved per query. |
| `RETRIEVAL_MIN_TOP_SIMILARITY` | `0.25` | Minimum cosine similarity of the top chunk. Queries where the best match falls below this are refused. |
| `RETRIEVAL_MIN_AVG_SIMILARITY` | `0.20` | Minimum average cosine similarity across the top window. Prevents answering when a single fluke match scores well but the rest score poorly. |
| `RETRIEVAL_AVG_WINDOW` | `5` | Number of top chunks used to compute the average similarity for confidence assessment. |

---

## Chat

| Variable | Default | Description |
|----------|---------|-------------|
| `CHAT_MAX_CONTEXT_CHUNKS` | `8` | Maximum number of chunks passed to the LLM as context. Increasing this improves recall on complex questions but increases token usage and cost. |
| `CHAT_MAX_OUTPUT_TOKENS` | `2048` | Token budget for LLM responses. |

---

## Chunking

These affect how documents are split before embedding. Changing them after documents are indexed requires re-ingestion; use `POST /admin/reindex` to re-embed existing chunks.

| Variable | Default | Description |
|----------|---------|-------------|
| `CHUNK_TARGET_TOKENS` | `512` | Target chunk size in tokens. Larger chunks carry more context but fewer fit in the LLM's context window. |
| `CHUNK_OVERLAP_TOKENS` | `64` | Token overlap between adjacent chunks. Prevents retrieval gaps at chunk boundaries. |
| `EMBEDDING_BATCH_SIZE` | `50` | Number of chunks submitted per embedding API call. Reduce if you hit rate limits. |
| `EMBEDDING_MAX_RETRIES` | `5` | Maximum retries on transient embedding failures (rate limits, connection errors). Retries use exponential backoff. |

---

## Upload

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_UPLOAD_SIZE_BYTES` | `52428800` (50 MB) | Maximum file size accepted by `POST /documents/upload`. Requests exceeding this are rejected with 413 before processing begins. |

---

## Curation — memory extraction

Memory extraction summarises a long conversation into a saved Markdown note. It is suggested automatically when a trigger condition is met (conversation length, topic shift, or session gap).

| Variable | Default | Description |
|----------|---------|-------------|
| `MEMORY_EXTRACTION_MIN_MESSAGES` | `12` | Minimum number of messages in a conversation before memory extraction is suggested. |
| `MEMORY_EXTRACTION_TOPIC_SHIFT_THRESHOLD` | `0.5` | Cosine similarity threshold between consecutive message embeddings below which a topic shift is detected. |
| `MEMORY_EXTRACTION_SESSION_BREAK_MINUTES` | `30` | Gap in minutes between consecutive messages that is treated as a session boundary. |

---

## Curation — duplicate detection

Near-duplicate detection runs automatically when a document is uploaded. If a new document's chunks are sufficiently similar to chunks in an existing document, the upload is flagged in the document's `duplicate_check` metadata.

| Variable | Default | Description |
|----------|---------|-------------|
| `DUPLICATE_DETECTION_ENABLED` | `true` | Enable or disable duplicate detection globally. |
| `DUPLICATE_NEAR_THRESHOLD` | `0.92` | Chunk embedding cosine similarity above which two chunks are considered near-duplicates. |
| `DUPLICATE_MATCH_RATIO` | `0.5` | Fraction of a document's chunks that must match another document for the document pair to be flagged. |

---

## Curation — gap analysis

Gap analysis runs after a low-confidence refusal. It uses the LLM to characterise what topic is missing and what types of documents would fill the gap.

| Variable | Default | Description |
|----------|---------|-------------|
| `GAP_ANALYSIS_ENABLED` | `true` | Enable or disable gap analysis on low-confidence query refusals. Disable to reduce LLM calls on refusals. |

---

## Operational

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Python logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR`. |
| `ENVIRONMENT` | `dev` | Runtime environment tag. No behavioural effect in current code. Useful for distinguishing log streams. |
| `NEXT_PUBLIC_BACKEND_URL` | `http://localhost:8000` | Backend URL as seen from the browser. Change this to your backend's public URL when deploying behind a reverse proxy. |
