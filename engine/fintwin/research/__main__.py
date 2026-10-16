"""Sharded research runs (free GitHub Actions runners, or locally).

python -m fintwin.research shard 3 16      # shard 3 of 16 -> .cache/research/<ticker>.json
python -m fintwin.research stats           # merge shards -> docs/paper/research.json
"""

from __future__ import annotations

import json
import sys
import time
import warnings
from pathlib import Path

import pandas as pd

from .. import universe

CACHE = Path(__file__).resolve().parents[2] / ".cache" / "research"
BANKRUPT = Path(__file__).resolve().parents[1] / "data" / "bankruptcies_2020.csv"


def research_tickers() -> list[str]:
    return universe.tickers() + pd.read_csv(BANKRUPT)["key"].tolist()


def shard(i: int, n: int) -> None:
    from ..export import _clean
    from .experiments import company

    CACHE.mkdir(parents=True, exist_ok=True)
    for k, t in enumerate(research_tickers()):
        if k % n != i:
            continue
        t0 = time.time()
        try:
            res = company(t)
        except Exception as e:  # keep the shard going; the failure is recorded
            res = {"ticker": t, "errors": {"company": f"{type(e).__name__}: {e}"}}
        (CACHE / f"{t.replace('~', '_')}.json").write_text(json.dumps(_clean(res)), encoding="utf-8")
        print(
            f"  {t}: {len(res.get('panel', []))} panel rows, {len(res.get('forecasts', []))} forecasts, "
            f"{len(res.get('errors', {}))} errors ({time.time() - t0:.0f}s)",
            flush=True,
        )


if __name__ == "__main__":
    warnings.simplefilter("ignore")
    if sys.argv[1] == "shard":
        shard(int(sys.argv[2]), int(sys.argv[3]))
    elif sys.argv[1] == "stats":
        from .stats import main

        main(CACHE)
    else:
        raise SystemExit(f"unknown command {sys.argv[1]}")
