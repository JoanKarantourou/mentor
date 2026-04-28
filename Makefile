.PHONY: test test-backend test-frontend test-e2e

# Run all tests (backend + frontend). E2E is opt-in via RUN_E2E=1.
test: test-backend test-frontend
ifdef RUN_E2E
test: test-e2e
endif

# Backend unit/integration tests (inside docker compose backend container)
test-backend:
	docker compose exec backend python -m pytest tests/ -v --tb=short

# Frontend unit tests (inside docker compose frontend container)
test-frontend:
	docker compose exec frontend npm test -- --run

# E2E tests — spins up stack, runs suite, tears down
# Usage: make test-e2e  or  RUN_E2E=1 make test
test-e2e:
	bash scripts/run-e2e.sh
