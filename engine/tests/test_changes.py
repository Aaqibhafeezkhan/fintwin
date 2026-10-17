import xml.etree.ElementTree as ET

from fintwin.changes import diff, rss, update_history


def _entry(health, quarter="2026-06-30", comps=None, stress=20.0):
    return {
        "name": "Co",
        "sector": "Industrials",
        "last_quarter": quarter,
        "matrix": {"base": {"health": health, "p_breach": 0.01}, "pandemic": {"health": stress, "p_breach": 0.5}},
        "components": comps,
    }


def test_diff_flags_material_moves_and_explains_them():
    prev = {
        "meta": {"generated": "2026-10-12"},
        "companies": {
            "AAA": _entry(70, comps={"liq": 80, "cov": 70, "lev": 60, "solv": 70}),
            "BBB": _entry(50),
            "CCC": _entry(40, quarter="2026-03-31"),
            "OLD": _entry(30),
        },
    }
    new = {
        "meta": {"generated": "2026-10-19"},
        "companies": {
            "AAA": _entry(58, quarter="2026-09-30", comps={"liq": 50, "cov": 70, "lev": 60, "solv": 65}),
            "BBB": _entry(53),  # below the threshold
            "CCC": _entry(47, quarter="2026-06-30"),
            "NEW": _entry(60),
        },
    }
    w = diff(prev, new, today="2026-10-19")
    assert [m["ticker"] for m in w["movers"]] == ["AAA", "CCC"]  # weakest first
    aaa = w["movers"][0]
    assert aaa["delta"] == -12 and aaa["new_filing"]
    # 0.3 x (50 - 80) = -9 points from liquidity, 0.2 x (65 - 70) = -1 from solvency
    assert aaa["drivers"][0] == {"component": "liq", "label": "liquidity runway", "points": -9.0}
    assert (w["n_weaker"], w["n_stronger"], w["n_new_filings"]) == (1, 1, 2)
    assert w["added"] == ["NEW"] and w["removed"] == ["OLD"]


def test_history_replaces_reruns_and_feed_is_valid_rss():
    w1 = {"date": "2026-10-12", "n_weaker": 0, "n_stronger": 0, "n_new_filings": 3, "movers": []}
    w2 = {
        "date": "2026-10-19",
        "n_weaker": 1,
        "n_stronger": 0,
        "n_new_filings": 1,
        "movers": [
            {
                "ticker": "AAA",
                "name": "A & Co",
                "health_before": 70,
                "health_after": 58,
                "new_filing": True,
                "quarter": "2026-09-30",
                "drivers": [{"label": "liquidity runway", "points": -9.0}],
            }
        ],
    }
    h = update_history(update_history(update_history(None, w1), w2), {**w2, "n_weaker": 2})
    assert [w["date"] for w in h["weeks"]] == ["2026-10-19", "2026-10-12"] and h["weeks"][0]["n_weaker"] == 2
    root = ET.fromstring(rss(h))
    items = root.findall("./channel/item")
    assert len(items) == 2 and "2 weaker" in items[0].find("title").text
    assert "A &amp; Co" in items[0].find("description").text or "A & Co" in items[0].find("description").text
