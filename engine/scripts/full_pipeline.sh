#!/usr/bin/env bash
# Everything, memory-friendly: rolling validation (2 workers) -> aggregate -> all company snapshots -> goldens -> backtests.
set -uo pipefail
cd "$(dirname "$0")/.."
export OPENBLAS_NUM_THREADS=1 PYTHONWARNINGS=ignore
rm -rf .cache/batch && mkdir -p .cache/batch
L=$(uv run python -c "from fintwin.backtest.batch import UNIVERSE_XL; print(' '.join(dict.fromkeys(UNIVERSE_XL)))")
R=$(echo $L | tr ' ' '\n' | tac | tr '\n' ' ')
work() { for t in $1; do [ -f ".cache/batch/$t.json" ] && continue; for a in 1 2 3; do uv run python -m fintwin.backtest.batch "$t" && break; sleep 5; done; done; }
work "$L" > .cache/validate.log 2>&1 &
work "$R" > .cache/validate2.log 2>&1
wait
work "$L" >> .cache/validate.log 2>&1   # pick up anything a worker dropped
echo "== validation aggregate"; uv run python -m fintwin.backtest.batch --aggregate
touch .cache/build_started
echo "== company snapshots"; bash scripts/resume_build.sh .cache/build_started > .cache/build.log 2>&1
grep -c "health" .cache/build.log; grep -E "FAILED|Traceback" .cache/build.log | tail -5
echo "== pipeline done"
