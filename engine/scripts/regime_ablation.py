"""Ablation: forecast backtest with vs without the recession regime (same shocks, same cutoffs)."""
import json
import sys

import numpy as np
import pandas as pd

import fintwin.scenarios.presets as presets
from fintwin.backtest import walk_forward as wf

TICKERS = sys.argv[1:] or ["AAPL", "TSLA", "CCL", "BA", "INTC", "NFLX"]


def aggregate(flag: bool) -> dict:
    presets.DEFAULT_LEVERS["recessions"] = flag
    rows = []
    for t in TICKERS:
        for ck in wf.CUTOFFS:
            r = wf.forecast_backtest(t, ck)
            for var, s in r["scores"].items():
                rows.append({"var": var, "cov50": s["coverage50"], "cov90": s["coverage90"], "skill": s["crps_skill"],
                             "crps": s["crps"], "n": s["n"]})
    df = pd.DataFrame(rows)
    return {v: {"coverage50": round(float(np.average(g.cov50, weights=g.n)), 3),
                "coverage90": round(float(np.average(g.cov90, weights=g.n)), 3),
                "median_crps_skill": round(float(g.skill.median()), 3),
                "share_beating_baseline": round(float((g.skill > 0).mean()), 3)} for v, g in df.groupby("var")}


out = {"without_regime": aggregate(False), "with_regime": aggregate(True)}
print(json.dumps(out, indent=1))
json.dump(out, open("../web/public/data/ablation_regime.json", "w"), indent=1)
