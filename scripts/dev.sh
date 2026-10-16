#!/usr/bin/env bash
# Local dev: live-ticker API + dashboard with hot reload.
set -euo pipefail
cd "$(dirname "$0")/.."
(cd engine && uv run --extra api python -m fintwin.api) &
cd web && npm run dev
