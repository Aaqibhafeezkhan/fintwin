#!/usr/bin/env bash
# Large-sample validation: rolling-origin forecasts + COVID cross-section for ~100 companies, then pool.
set -uo pipefail
cd "$(dirname "$0")/.."
export OPENBLAS_NUM_THREADS=1 PYTHONWARNINGS=ignore
TICKERS=$(uv run python -c "from fintwin.backtest.batch import UNIVERSE_XL; print(' '.join(UNIVERSE_XL))")
for t in $TICKERS; do
  [ -f ".cache/batch/$t.json" ] && [ "${FORCE:-0}" != "1" ] && continue
  for attempt in 1 2 3; do uv run python -m fintwin.backtest.batch "$t" && break; sleep 3; done
done
uv run python -m fintwin.backtest.batch --aggregate
