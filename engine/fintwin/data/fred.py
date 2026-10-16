"""FRED macro series via the public CSV endpoint (no API key), cached on disk."""
from __future__ import annotations

import io
import time
from pathlib import Path

import pandas as pd
import requests

CACHE_DIR = Path(__file__).resolve().parents[2] / ".cache" / "fred"
SERIES = {
    "short_rate": "DGS3MO",    # 3-month Treasury, % p.a.
    "long_rate": "DGS10",      # 10-year Treasury, % p.a.
    "credit_spread": "BAA10Y", # Moody's Baa minus 10y Treasury, % p.a.
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
