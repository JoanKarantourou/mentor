# Contributing

## Development environment

Follow the local development setup in [DEPLOYMENT.md](DEPLOYMENT.md#local-development):

```bash
cp .env.example .env
docker compose up
```

The stack comes up with stub providers — no API keys needed for development.

## Running tests

```bash
make test            # backend + frontend (requires running stack)
make test-backend    # backend unit/integration tests only
make test-frontend   # frontend unit tests only
RUN_E2E=1 make test  # adds E2E tests (slow; spins up and tears down the full stack)
```

## Code style

**Python:** [`ruff`](https://docs.astral.sh/ruff/) for linting and formatting. From `backend/`:

```bash
ruff check .
ruff format .
```

**TypeScript/React:** ESLint + Prettier as configured in `frontend/`. From `frontend/`:

```bash
npm run lint
```

## Commit style

No enforced convention. Short, present-tense summaries are preferred:

- `add gap analysis endpoint` not `added gap analysis endpoint`
- `fix duplicate detection threshold logic` not `fixed the bug in duplicate detection`

## Pull requests

- Describe what the change does and why.
- Note how you tested it (manual steps or automated tests added).
- Keep PRs focused — one logical change per PR makes review easier.

## Note on response time

This is a personal project. PR review is best-effort with no SLA. Contributions are welcome, but don't count on a fast turnaround.
