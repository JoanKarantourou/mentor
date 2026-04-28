#!/usr/bin/env bash
# Run the end-to-end test suite.
# Usage:
#   ./scripts/run-e2e.sh             # full suite (brings up docker compose)
#   E2E_SKIP_COMPOSE=1 ./scripts/run-e2e.sh  # against an already-running stack

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "=== Running E2E tests ==="
python -m pytest e2e/ -v --tb=short "$@"
echo "=== E2E tests complete ==="
