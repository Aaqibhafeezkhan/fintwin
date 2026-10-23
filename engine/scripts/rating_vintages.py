"""Point-in-time rating-spread tables: Damodaran's ratings page as archived by the Wayback Machine each year.

    uv run python scripts/rating_vintages.py      # -> engine/fintwin/data/rating_spreads.csv

Damodaran updates the table in January. For each year we take the last snapshot on or before 15 February (the
research cutoffs), else the first snapshot of that year before 1 July (the January table, archived late), and record
which snapshot was used. Only the table for large non-financial firms is kept, as in fintwin.model.ratings.
"""

import io
import time
from pathlib import Path

import pandas as pd
import requests

OUT = Path(__file__).resolve().parents[1] / "fintwin" / "data" / "rating_spreads.csv"
PAGES = ["pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/ratings.htm",
         "pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/ratings.html"]
ORDER = ["AAA", "AA", "A+", "A", "A-", "BBB", "BB+", "BB", "B+", "B", "B-", "CCC", "CC", "C", "D"]


def get(url: str, **kw) -> requests.Response:
    """The Wayback Machine refuses bursts of connections: retry with a growing pause."""
    for k in range(6):
        try:
            r = requests.get(url, timeout=60, **kw)
            if r.status_code == 200:
                return r
        except requests.RequestException:
            pass
        time.sleep(15 * (k + 1))
    raise RuntimeError(f"Wayback unavailable: {url}")


def snapshots(year: int) -> list[str]:
    out = []
    for page in PAGES:
        r = get("https://web.archive.org/cdx/search/cdx",
                         params={"url": page, "from": f"{year}0101", "to": f"{year}0630", "output": "json",
                                 "filter": "statuscode:200"})
        rows = r.json()[1:] if r.text.strip() else []
        out += [(row[1], row[2]) for row in rows]
        time.sleep(1)
    return sorted(out)


def table(ts: str, original: str) -> list[float]:
    html = get(f"https://web.archive.org/web/{ts}id_/{original}").text
    t = pd.read_html(io.StringIO(html))[0]
    spreads = {}
    for _, row in t.iterrows():
        rating = str(row.iloc[2])
        code = rating.split("/")[-1].strip()
        if code in ORDER and code not in spreads:
            spreads[code] = float(str(row.iloc[3]).replace("%", "").strip()) / 100
        if len(spreads) == len(ORDER):
            break
    if len(spreads) != len(ORDER):
        raise ValueError(f"{ts}: parsed {len(spreads)} ratings")
    return [spreads[c] for c in ORDER]


if __name__ == "__main__":
    done = pd.read_csv(OUT) if OUT.exists() else pd.DataFrame(columns=["year"])
    rows = done.to_dict("records")
    for year in range(2013, 2027):
        if year in set(done["year"]):
            continue
        snaps = snapshots(year)
        before = [s for s in snaps if s[0][:8] <= f"{year}0215"]
        pick = before[-1] if before else (snaps[0] if snaps else None)
        if pick is None:
            print(year, "no snapshot")
            continue
        vals = table(*pick)
        rows.append({"year": year, "snapshot": pick[0], "before_cutoff": bool(before), **dict(zip(ORDER, vals, strict=True))})
        print(year, pick[0], vals[:6], flush=True)
        pd.DataFrame(rows).sort_values("year").to_csv(OUT, index=False)
        time.sleep(3)
