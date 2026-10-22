"""Sharded research runs (free GitHub Actions runners, or locally).

python -m fintwin.research prefetch          # download every company's XBRL facts once (SEC rate limit: serial)
python -m fintwin.research shard 3 16      # shard 3 of 16 -> .cache/research/<key>.json
python -m fintwin.research stats           # merge shards -> docs/paper/research.json

The sample is the survivorship-free EDGAR universe (data/universe_edgar.csv): every non-financial XBRL filer with
$50M+ revenue in some year 2012-2024, keyed by CIK. Probabilistic forecasts, which need ETS fits and are not about
survivorship, run for S&P 500 members (today's and those of 20 February 2020) only.
"""

from __future__ import annotations

import json
import sys
import time
import warnings
from pathlib import Path

import pandas as pd

CACHE = Path(__file__).resolve().parents[2] / ".cache" / "research"
DATA = Path(__file__).resolve().parents[1] / "data"


def research_tickers() -> list[str]:
    return pd.read_csv(DATA / "universe_edgar.csv")["key"].tolist()


def forecast_ciks() -> set[int]:
    today = pd.read_csv(DATA / "universe_sp500.csv")["cik"]
    then = pd.read_csv(DATA / "sp500_2020-02-20.csv")["cik"]
    return set(today.dropna().astype(int)) | set(then.astype(int))


def prefetch() -> None:
    from ..data.facts import company_facts

    keys = research_tickers()
    for k, t in enumerate(keys):
        try:
            company_facts(int(t[3:]))
        except Exception as e:
            print(f"  {t}: {type(e).__name__}: {e}", flush=True)
        if k % 250 == 0:
            print(f"  {k}/{len(keys)}", flush=True)


def shard(i: int, n: int) -> None:
    from ..export import _clean
    from .experiments import company

    CACHE.mkdir(parents=True, exist_ok=True)
    fc = forecast_ciks()
    for k, t in enumerate(research_tickers()):
        if k % n != i:
            continue
        out = CACHE / f"{t}.json"
        if out.exists():  # resumable
            continue
        t0 = time.time()
        try:
            res = company(t, with_forecasts=int(t[3:]) in fc)
        except Exception as e:  # keep the shard going; the failure is recorded
            res = {"ticker": t, "errors": {"company": f"{type(e).__name__}: {e}"}}
        out.write_text(json.dumps(_clean(res)), encoding="utf-8")
        print(
            f"  {t}: {len(res.get('panel', []))} panel rows, {len(res.get('forecasts', []))} forecasts, "
            f"{len(res.get('errors', {}))} errors ({time.time() - t0:.0f}s)",
            flush=True,
        )


if __name__ == "__main__":
    warnings.simplefilter("ignore")
    if sys.argv[1] == "prefetch":
        prefetch()
    elif sys.argv[1] == "shard":
        shard(int(sys.argv[2]), int(sys.argv[3]))
    elif sys.argv[1] == "stats":
        from .stats import main

        main(CACHE)
    else:
        raise SystemExit(f"unknown command {sys.argv[1]}")
