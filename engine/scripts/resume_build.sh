#!/usr/bin/env bash
# Rebuild only companies whose snapshot is older than a reference file (resume after an interrupted build_all).
set -uo pipefail
cd "$(dirname "$0")/.."
export OPENBLAS_NUM_THREADS=1 PYTHONWARNINGS=ignore
REF=${1:-.cache/build_started}
TICKERS=$(uv run python -c "from fintwin.export import SHOWCASE; from fintwin.backtest.walk_forward import UNIVERSE; from fintwin.backtest.batch import UNIVERSE_XL; print(' '.join(dict.fromkeys(SHOWCASE + UNIVERSE + UNIVERSE_XL)))")
for t in $TICKERS; do
  f="../web/public/data/companies/$t.json"
  [ -f "$f" ] && [ "$f" -nt "$REF" ] && continue
  for attempt in 1 2 3; do uv run python -m fintwin.export "$t" && break; sleep 5; done
done
uv run python -m fintwin.export GOLDEN
uv run python -m fintwin.export BACKTEST
uv run python -m fintwin.notes
