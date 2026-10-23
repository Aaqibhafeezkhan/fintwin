"""Completeness audit of the quarterly panels (fiscal calendars, missing quarters, latest filings).

    uv run python scripts/data_audit.py            # -> docs/paper/data_audit.json

For every company in the EDGAR research universe: gaps longer than 126 days in the quarter spine, quarters whose
revenue or operating cash flow could not be recovered, and whether the last quarter in the panel matches the last
10-Q / 10-K the company filed (a check that the latest forms are read, whatever the fiscal calendar). The same audit
under the old 75-105 day quarter window measures what the 52/53-week fix recovered.
"""

import json
import sys
import warnings
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "engine"))
warnings.simplefilter("ignore")

import fintwin.data.facts as F  # noqa: E402
from fintwin.data.edgar_universe import submissions  # noqa: E402

UNIVERSE = ROOT / "engine" / "fintwin" / "data" / "universe_edgar.csv"
OUT = ROOT / "docs" / "paper" / "data_audit.json"


def audit(key: str, cik: int) -> dict:
    q = F.load_company(key).quarters
    idx = q.index
    gaps = (idx[1:] - idx[:-1]).days
    f = submissions(cik)["filings"]
    per = f[f["form"].isin(["10-Q", "10-K", "10-KT", "10-Q/A", "10-K/A"])]
    # why each remaining gap exists: no periodic filing for a period inside it, or a filing without a revenue fact
    reports = pd.to_datetime(per["reportDate"].replace("", None)).dropna()
    no_filing = tagging = 0
    for i in range(len(idx) - 1):
        if gaps[i] > 126:
            inside = reports[
                (reports > idx[i] + pd.Timedelta(days=14)) & (reports < idx[i + 1] - pd.Timedelta(days=14))
            ]
            if len(inside):
                tagging += 1
            else:
                no_filing += 1
    last_report = pd.to_datetime(per["reportDate"].replace("", None)).max() if len(per) else pd.NaT
    lag = abs((idx[-1] - last_report).days) if pd.notna(last_report) and len(idx) else None
    return {
        "n_quarters": int(len(q)),
        "gaps_over_126d": int((gaps > 126).sum()),
        "gaps_no_filing": no_filing,
        "gaps_filed_untagged": tagging,
        "rev_missing": int(q["revenue"].isna().sum()),
        "cfo_missing": int(q["cfo"].isna().sum()),
        "latest_matches_last_filing": bool(lag is not None and lag <= 14),
    }


def run(window: tuple[int, int]) -> pd.DataFrame:
    F.QUARTER_DAYS = window
    u = pd.read_csv(UNIVERSE)
    rows = []
    for r in u.itertuples():
        try:
            rows.append({"key": r.key, **audit(r.key, int(r.cik))})
        except Exception as e:  # unusable filers (no us-gaap revenue) are counted, not fatal
            rows.append({"key": r.key, "error": type(e).__name__})
        F.company_facts.cache_clear()
    return pd.DataFrame(rows)


def summary(d: pd.DataFrame) -> dict:
    ok = d[d.get("error").isna()] if "error" in d else d
    return {
        "companies": int(len(d)),
        "loaded": int(len(ok)),
        "firm_quarters": int(ok["n_quarters"].sum()),
        "companies_with_gaps": int((ok["gaps_over_126d"] > 0).sum()),
        "gaps": int(ok["gaps_over_126d"].sum()),
        "gaps_no_filing": int(ok["gaps_no_filing"].sum()) if "gaps_no_filing" in ok else None,
        "gaps_filed_untagged": int(ok["gaps_filed_untagged"].sum()) if "gaps_filed_untagged" in ok else None,
        "share_latest_matches_last_filing": float(ok["latest_matches_last_filing"].mean()),
        "cfo_missing_quarters": int(ok["cfo_missing"].sum()),
    }


if __name__ == "__main__":
    new, old = run((75, 126)), run((75, 105))
    out = {"current": summary(new), "old_window_75_105": summary(old)}
    fixed = old.merge(new, on="key", suffixes=("_old", "_new"))
    out["companies_recovered"] = int(((fixed["gaps_over_126d_old"] > 0) & (fixed["gaps_over_126d_new"] == 0)).sum())
    out["examples_recovered"] = (
        fixed.loc[(fixed["gaps_over_126d_old"] > 0) & (fixed["gaps_over_126d_new"] == 0), "key"].head(20).tolist()
    )
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))
