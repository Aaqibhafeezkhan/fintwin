"""Print calibrated parameters and headline stress results for a set of tickers."""
import sys
import time

import numpy as np

from fintwin.data.facts import load_company
from fintwin.data.fred import macro_quarterly
from fintwin.scenarios.presets import PRESETS
from fintwin.stochastic.calibrate import calibrate
from fintwin.stochastic.mc import run, summarize

KEYS = ["mu", "phi", "sigma_g", "t_df", "v", "sigma_m", "dso", "dio", "dpo", "dep_rate", "capex_ratio",
        "ocf_ratio", "coupon", "bb_ratio", "tax_rate"]
tickers = sys.argv[1:] or ["AAPL", "TSLA", "CCL", "BA", "INTC", "NFLX"]
asof = None
if tickers and tickers[0].startswith("asof="):
    asof = tickers.pop(0)[5:]
macro = macro_quarterly(asof)
for t in tickers:
    p = calibrate(load_company(t, asof=asof), macro)
    print("==", t, p["last_quarter"], {k: round(p[k], 4) for k in KEYS},
          f"F={p['F']/1e9:.2f}bn cash={p['cash0']/1e9:.1f}bn debt={p['debt0']/1e9:.1f}bn rcf={p['revolver_cap']/1e9:.1f}bn")
    for s in ["base", "rates_200", "sales_20", "recession", "pandemic", "credit_crunch"]:
        t0 = time.time()
        out = run(p, PRESETS[s]["knobs"], n_paths=5000)
        sm = summarize(out)
        print(f"  {s:14s} health={sm['health_score']:5.1f} p_breach={sm['p_breach']:.3f} "
              f"p_icr<1.5={sm['p_icr_below_1_5']:.3f} subIG={sm['p_downgrade_below_ig']:.2f} "
              f"idgap={np.abs(out['identity_gap']).max():.1e} {time.time()-t0:.2f}s")
