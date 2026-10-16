"""Optional local API: build a twin for any ticker on demand.

    uv run --extra api python -m fintwin.api        # then the dashboard's dev server proxies /api here

The static dashboard works without it (it reads JSON snapshots); this only adds tickers outside the snapshot.
"""

from __future__ import annotations

import json
from functools import lru_cache

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response

from .data.fred import macro_quarterly
from .export import _clean, company_block

app = FastAPI(title="FinTwin live API")


@lru_cache(maxsize=32)
def _build(ticker: str) -> str:
    return json.dumps(_clean(company_block(ticker, macro_quarterly(), n_paths=3000)))


@app.get("/api/company/{ticker}")
def company(ticker: str) -> Response:
    t = ticker.upper().strip()
    if not t.replace(".", "").replace("-", "").isalnum() or len(t) > 10:
        raise HTTPException(400, "invalid ticker")
    try:
        return Response(_build(t), media_type="application/json")
    except KeyError as e:
        raise HTTPException(404, f"{t} is not a known SEC ticker") from e
    except Exception as e:  # data gaps for unusual filers (banks, foreign issuers, custom taxonomies)
        raise HTTPException(422, f"{t}: could not build a twin ({type(e).__name__}: {e})") from e


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8765)
