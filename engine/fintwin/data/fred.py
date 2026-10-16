"""FRED macro series via the public CSV endpoint (no API key), cached on disk."""

from __future__ import annotations

import io
import time
from pathlib import Path

import pandas as pd
import requests

CACHE_DIR = Path(__file__).resolve().parents[2] / ".cache" / "fred"
SERIES = {
    "short_rate": "DGS3MO",  # 3-month Treasury, % p.a.
    "long_rate": "DGS10",  # 10-year Treasury, % p.a.
    "credit_spread": "BAA10Y",  # Moody's Baa minus 10y Treasury, % p.a.
}


def fred_series(series_id: str, max_age_hours: float = 24) -> pd.Series:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{series_id}.csv"
    if not path.exists() or time.time() - path.stat().st_mtime > max_age_hours * 3600:
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        path.write_text(resp.text, encoding="utf-8")
    df = pd.read_csv(io.StringIO(path.read_text(encoding="utf-8")))
    s = pd.to_numeric(df.iloc[:, 1], errors="coerce")
    s.index = pd.to_datetime(df.iloc[:, 0])
    return s.dropna() / 100.0


def macro_quarterly(asof: str | None = None) -> pd.DataFrame:
    """Quarter-average rates in decimal form, truncated at `asof`."""
    df = pd.DataFrame({k: fred_series(v) for k, v in SERIES.items()})
    if asof:
        df = df[df.index <= pd.Timestamp(asof)]
    return df.resample("QE").mean().dropna()


def recession_regime(asof: str | None = None) -> dict:
    """Markov recession regime from NBER-dated US recessions (FRED USREC) and nominal GDP, post-1947.

    Returns quarterly entry hazard, exit probability, the nominal-GDP growth shortfall per recession quarter,
    whether the economy is in recession at `asof`, and quarterly YoY nominal GDP growth for beta estimation.
    """
    rec = (fred_series("USREC") * 100).resample("QE").max()
    gdp = (fred_series("GDP") * 100).resample("QE").last()
    if asof:
        rec, gdp = rec[rec.index <= pd.Timestamp(asof)], gdp[gdp.index <= pd.Timestamp(asof)]
    rec = rec[rec.index >= "1947-01-01"]
    starts = int(((rec == 1) & (rec.shift(1) == 0)).sum())
    in_rec = float(rec.sum())
    yoy = (gdp.apply(lambda x: __import__("math").log(x)).diff(4)).dropna()
    r = rec.reindex(yoy.index, method="nearest")
    shortfall_q = float(yoy[r == 0].mean() - yoy[r == 1].mean()) / 4.0
    return {
        "hazard": starts / max(len(rec) - in_rec, 1.0),
        "exit": starts / max(in_rec, 1.0),
        "gdp_shortfall_q": shortfall_q,
        "in_recession_now": bool(rec.iloc[-1] == 1) if len(rec) else False,
        "gdp_yoy": yoy,
        "n_recessions": starts,
    }
