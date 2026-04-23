# Mentor — backend

FastAPI backend for the Mentor RAG assistant.

## Running locally (Docker)

```bash
docker compose up --build
```

## Uploading a file

```bash
# Upload a file and get back a document ID
curl -X POST http://localhost:8000/documents/upload -F "file=@report.pdf"
# {"document_id": "...", "status": "pending"}

# Poll status (processing happens in the background)
curl http://localhost:8000/documents/<id>

# Fetch the normalized Markdown once status is "ready"
curl http://localhost:8000/documents/<id>/content

# List all documents (excludes soft-deleted)
curl http://localhost:8000/documents

# Soft-delete
curl -X DELETE http://localhost:8000/documents/<id>
```

## Providers

| Variable | Default | Options |
|----------|---------|---------|
| `EMBEDDING_PROVIDER` | `stub` | `stub`, `azure_openai` |
| `LLM_PROVIDER` | `stub` | `stub` (more coming in Stage 5) |

The stub providers require no credentials and are the default for local development.

## Migrations

```bash
# Apply all pending migrations
docker compose exec backend alembic upgrade head

# Check current revision
docker compose exec backend alembic current

# Create a new migration after changing models
docker compose exec backend alembic revision --autogenerate -m "describe your change"

# Roll back one step
docker compose exec backend alembic downgrade -1
```

## Running tests

```bash
docker compose exec backend pytest -v
```

## Linting

```bash
docker compose exec backend ruff check .
docker compose exec backend ruff format --check .
```

## Known limitations

- No LLM chat or retrieval (Stage 5).
- No authentication — `uploaded_by` is hardcoded to `"dev"` (deferred).
- Direct OpenAI and Anthropic providers not yet implemented (Stage 5).
- Azure Blob Storage adapter not yet implemented (only `LocalBlobStore`).
- Language detection supports English and Greek. Adding more languages is a one-line change in `language.py`.
