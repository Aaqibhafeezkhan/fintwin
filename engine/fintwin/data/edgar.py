"""Minimal SEC EDGAR client: ticker lookup and XBRL company facts, with disk cache.

SEC fair-access rules: declare a User-Agent with contact info and stay under 10 requests/s.
data.sec.gov does not send CORS headers, so this always runs server-side / offline.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]
CACHE_DIR = Path(__file__).resolve().parents[2] / ".cache" / "edgar"
load_dotenv(ROOT / ".env")

_MIN_INTERVAL = 0.15  # seconds between requests (< 10 req/s)
_last_request = 0.0


def _user_agent() -> str:
    ua = os.environ.get("SEC_USER_AGENT")
    if not ua:
        raise RuntimeError("Set SEC_USER_AGENT in .env (e.g. 'FinTwin research you@example.com')")
    return ua


def _get_json(url: str, cache_name: str, max_age_hours: float) -> dict:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / cache_name
    if path.exists() and (time.time() - path.stat().st_mtime) < max_age_hours * 3600:
        return json.loads(path.read_text(encoding="utf-8"))

    global _last_request
    wait = _MIN_INTERVAL - (time.time() - _last_request)
    if wait > 0:
        time.sleep(wait)
    resp = requests.get(url, headers={"User-Agent": _user_agent(), "Accept-Encoding": "gzip, deflate"}, timeout=60)
    _last_request = time.time()
    resp.raise_for_status()
    data = resp.json()
    path.write_text(json.dumps(data), encoding="utf-8")
    return data


def ticker_to_cik(ticker: str) -> tuple[int, str]:
    """Return (cik, company title) for a ticker."""
    data = _get_json("https://www.sec.gov/files/company_tickers.json", "company_tickers.json", 24 * 7)
    t = ticker.upper()
    for row in data.values():
        if row["ticker"].upper() == t:
            return int(row["cik_str"]), row["title"]
    raise KeyError(f"Unknown ticker: {ticker}")


def company_facts(cik: int, max_age_hours: float = 24) -> dict:
    return _get_json(
        f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json",
        f"companyfacts_{cik:010d}.json",
        max_age_hours,
    )


def filing_url(cik: int, accn: str) -> str:
    """Human-readable link to the filing index for provenance."""
    return f"https://www.sec.gov/Archives/edgar/data/{cik}/{accn.replace('-', '')}/{accn}-index.htm"
