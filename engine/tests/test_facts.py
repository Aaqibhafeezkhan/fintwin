import pandas as pd

from fintwin.data.facts import duration_quarters, instant_values, season_of


def fact(start, end, val, filed, accn="a", form="10-Q"):
    return {"start": start, "end": end, "val": val, "filed": filed, "accn": accn, "form": form, "fy": 2024, "fp": "Q"}


def gaap(tag, rows):
    return {tag: {"units": {"USD": rows}}}


def test_ytd_cash_flows_are_decumulated():
    rows = [
        fact("2024-01-01", "2024-03-31", 100, "2024-04-30"),
        fact("2024-01-01", "2024-06-30", 250, "2024-07-30"),   # H1 YTD
        fact("2024-01-01", "2024-09-30", 330, "2024-10-30"),   # 9M YTD
        fact("2024-01-01", "2024-12-31", 500, "2025-02-15", form="10-K"),
    ]
    q = duration_quarters(gaap("X", rows), "X")
    vals = {k.date().isoformat(): v[0] for k, v in q.items()}
    assert vals == {"2024-03-31": 100, "2024-06-30": 150, "2024-09-30": 80, "2024-12-31": 170}


def test_point_in_time_ignores_later_restatement():
    rows = [
        fact("2024-01-01", "2024-03-31", 100, "2024-04-30", accn="orig"),
        fact("2024-01-01", "2024-03-31", 90, "2025-04-30", accn="restated"),
    ]
    g = gaap("X", rows)
    assert duration_quarters(g, "X", pd.Timestamp("2024-12-31"))[pd.Timestamp("2024-03-31")] == (100.0, "orig")
    assert duration_quarters(g, "X")[pd.Timestamp("2024-03-31")] == (90.0, "restated")


def test_facts_filed_after_asof_are_invisible():
    rows = [{"end": "2024-03-31", "val": 5, "filed": "2024-05-01", "accn": "a", "form": "10-Q"}]
    assert instant_values(gaap("C", rows), "C", pd.Timestamp("2024-04-30")) == {}


def test_season_handles_52_53_week_calendars():
    # Apple-style fiscal quarter ending on April 1 belongs with March quarter ends.
    assert season_of(pd.Timestamp("2023-04-01")) == season_of(pd.Timestamp("2024-03-30"))
    assert season_of(pd.Timestamp("2023-12-30")) == season_of(pd.Timestamp("2022-12-31"))
