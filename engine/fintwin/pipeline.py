"""Sharded build pipeline, designed for free GitHub Actions runners (and runnable locally).

    python -m fintwin.pipeline norms                 # sector leverage norms for the whole universe
    python -m fintwin.pipeline shard 3 10            # shard 3 of 10: company snapshots, validation, time machine
    python -m fintwin.pipeline aggregate             # index, calibration, backtests, goldens, notes

Each shard writes self-contained files, so shards can run in parallel on separate machines and be merged by
simply copying their output directories together before `aggregate`.
"""

from __future__ import annotations

import json
import sys
import time
import traceback
import warnings
from datetime import date
from pathlib import Path

import numpy as np

from . import universe
from .data.facts import load_company

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "web" / "public" / "data"
CACHE = Path(__file__).resolve().parents[1] / ".cache"


def _json(path: Path, obj) -> None:
    from .export import _clean

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_clean(obj), separators=(",", ":")), encoding="utf-8")


def norms() -> None:
    lev: dict[str, float] = {}
    for t in universe.tickers():
        try:
            q = load_company(t).quarters
            ebitda = float((q["operating_income"] + q["da"].fillna(0)).tail(4).sum())
            nd = float(q["total_debt"].iloc[-1] - q["cash"].iloc[-1] - q["short_investments"].iloc[-1])
            if ebitda > 0 and np.isfinite(nd):
                lev[t] = nd / ebitda
        except Exception as e:
            print(f"  norms skip {t}: {type(e).__name__}: {e}")
    out = universe.compute_norms(lev)
    print(json.dumps(out["tolerance"], indent=1), f"n={out['n']}")


def shard(i: int, n: int) -> None:
    from .backtest.batch import company_cases
    from .data.fred import macro_quarterly
    from .export import SHOWCASE, SOBOL_SET, company_block

    tickers = [
        t for k, t in enumerate(universe.tickers() + [s for s in SHOWCASE if s not in universe.tickers()]) if k % n == i
    ]
    macro = macro_quarterly()
    failed = {}
    for t in tickers:
        t0 = time.time()
        try:
            block = company_block(t, macro, with_sobol=t in SOBOL_SET)
            _json(DATA / "companies" / f"{t}.json", block)
            res = company_cases(t)
            _json(DATA / "timeline" / f"{t}.json", res.pop("timeline"))
            _json(CACHE / "batch" / f"{t}.json", res)
            print(
                f"  {t}: health {block['presets']['base']['health_score']:.0f}, {len(res['cases'])} forecasts ({time.time() - t0:.0f}s)"
            )
        except Exception as e:
            failed[t] = f"{type(e).__name__}: {e}"
            print(f"  {t}: FAILED {failed[t]}")
            traceback.print_exc(limit=2)
    _json(CACHE / "failed" / f"shard{i}.json", failed)


def build_index() -> dict:
    from .export import SHOWCASE, meta_block

    companies = {}
    for f in sorted((DATA / "companies").glob("*.json")):
        b = json.loads(f.read_text(encoding="utf-8"))
        companies[b["ticker"]] = {
            "name": b["name"],
            "sector": b["sector"],
            "gics": b.get("gics", ""),
            "showcase": b["ticker"] in SHOWCASE,
            "last_quarter": b["params"]["last_quarter"],
            "matrix": {k: {"health": v["health_score"], "p_breach": v["p_breach"]} for k, v in b["presets"].items()},
        }
    index = {
        "companies": companies,
        "meta": {**meta_block(), "generated": date.today().isoformat(), "n_companies": len(companies)},
    }
    _json(DATA / "index.json", index)
    return index


def aggregate() -> None:
    from .backtest.batch import aggregate as calib
    from .data.fred import macro_quarterly
    from .export import build_backtests, golden_cases
    from .notes import build as notes

    idx = build_index()
    print(f"  index: {len(idx['companies'])} companies")
    r = calib()
    print(
        f"  calibration: {r['n_companies']} companies, {r['n_forecasts']} forecasts, rho={r['cross_section']['spearman']:.2f}"
    )
    golden_cases(macro_quarterly())
    build_backtests()
    notes()
    failed = {}
    for f in (CACHE / "failed").glob("*.json"):
        failed.update(json.loads(f.read_text(encoding="utf-8")))
    _json(
        DATA / "build_report.json",
        {"generated": date.today().isoformat(), "failed": failed, "n_companies": len(idx["companies"])},
    )
    print(f"  failed: {len(failed)} {list(failed)[:12]}")


if __name__ == "__main__":
    warnings.simplefilter("ignore")
    cmd = sys.argv[1]
    if cmd == "norms":
        norms()
    elif cmd == "shard":
        shard(int(sys.argv[2]), int(sys.argv[3]))
    elif cmd == "aggregate":
        aggregate()
    else:
        raise SystemExit(f"unknown command {cmd}")
