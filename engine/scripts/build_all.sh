#!/usr/bin/env bash
# Rebuild every dashboard data file. One company per Python process keeps peak memory low.
set -euo pipefail
cd "$(dirname "$0")/.."
export OPENBLAS_NUM_THREADS=1 PYTHONWARNINGS=ignore
TICKERS=$(uv run python -c "from fintwin.export import SHOWCASE; from fintwin.backtest.walk_forward import UNIVERSE; from fintwin.backtest.batch import UNIVERSE_XL; print(' '.join(dict.fromkeys(SHOWCASE + UNIVERSE + UNIVERSE_XL)))")
for t in $TICKERS; do
  for attempt in 1 2 3; do uv run python -m fintwin.export "$t" && break; sleep 2; done
done
uv run python -m fintwin.export GOLDEN
uv run python -m fintwin.export BACKTEST
