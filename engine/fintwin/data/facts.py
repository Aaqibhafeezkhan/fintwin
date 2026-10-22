"""Turn raw XBRL company facts into a clean quarterly panel.

Three problems this module solves:
1. Tag drift - companies switch tags over time (SalesRevenueNet -> RevenueFromContract...), so each
   field has an ordered list of fallback tags, merged period by period.
2. Year-to-date reporting - 10-Q cash-flow facts are cumulative and Q4 only exists inside the 10-K
   annual total. Discrete quarters are recovered by differencing facts that share a start date.
3. Look-ahead bias - restatements overwrite history. `asof` keeps only facts filed on or before a
   date, giving the point-in-time vintage an analyst would actually have seen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np
import pandas as pd

from .edgar import company_facts as _company_facts
from .edgar import ticker_to_cik


@lru_cache(maxsize=2)
def company_facts(cik: int) -> dict:
    return _company_facts(cik)


FORMS = {"10-K", "10-Q", "10-K/A", "10-Q/A", "10-KT", "20-F", "40-F"}
# A fiscal quarter is 12-14 weeks, but 52/53-week retailers run one 16- or 17-week quarter a year (Kroger's first,
# Costco's and AutoZone's fourth): anything from 11 to 18 weeks is one quarter.
QUARTER_DAYS = (75, 126)
ALIGN_TOLERANCE_DAYS = 12

# field -> ordered tag fallbacks. Duration concepts are flows over a period, instants are balances.
DURATION = {
    "revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
        "SalesRevenueServicesGross",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "SalesRevenueGoodsNet",
    ],
    "operating_income": ["OperatingIncomeLoss"],
    "pretax_income": [
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesDomestic",
    ],
    "da": [
        "DepreciationDepletionAndAmortization",
        "DepreciationAndAmortization",
        "DepreciationAmortizationAndAccretionNet",
        "Depreciation",
    ],
    "interest_expense": [
        "InterestExpense",
        "InterestExpenseNonoperating",
        "InterestAndDebtExpense",
        "InterestExpenseDebt",
    ],
    "tax": ["IncomeTaxExpenseBenefit"],
    "net_income": ["NetIncomeLoss", "ProfitLoss"],
    "sbc": ["ShareBasedCompensation", "AllocatedShareBasedCompensationExpense"],
    "cfo": [
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"],
    "dividends": ["PaymentsOfDividends", "PaymentsOfDividendsCommonStock"],
    "buybacks": ["PaymentsForRepurchaseOfCommonStock"],
    # non-cash impairments, added back to operating income (credit analysts' "adjusted EBIT")
    "imp_total": ["AssetImpairmentCharges"],
    "imp_gw_intang": ["GoodwillAndIntangibleAssetImpairment"],
    "imp_goodwill": ["GoodwillImpairmentLoss"],
    "imp_intangible": [
        "ImpairmentOfIntangibleAssetsExcludingGoodwill",
        "ImpairmentOfIntangibleAssetsIndefinitelivedExcludingGoodwill",
    ],
    "imp_longlived": ["ImpairmentOfLongLivedAssetsHeldForUse"],
}
INSTANT = {
    "cash": ["CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"],
    "short_investments": [
        "MarketableSecuritiesCurrent",
        "ShortTermInvestments",
        "AvailableForSaleSecuritiesDebtSecuritiesCurrent",
    ],
    "receivables": ["AccountsReceivableNetCurrent", "ReceivablesNetCurrent"],
    "inventory": ["InventoryNet", "InventoryNetOfAllowancesCustomerAdvancesAndProgressBillings"],
    "payables": [
        "AccountsPayableCurrent",
        "AccountsPayableTradeCurrent",
        "AccountsPayableAndAccruedLiabilitiesCurrent",
    ],
    "deferred_revenue": [
        "ContractWithCustomerLiabilityCurrent",
        "CustomerDepositsCurrent",
        "DeferredRevenueCurrent",
        "CustomerAdvancesCurrent",
    ],
    "ppe": [
        "PropertyPlantAndEquipmentNet",
        "PropertyPlantAndEquipmentAndFinanceLeaseRightOfUseAssetAfterAccumulatedDepreciationAndAmortization",
    ],
    "assets": ["Assets"],
    "liabilities": ["Liabilities"],
    "current_assets": ["AssetsCurrent"],
    "current_liabilities": ["LiabilitiesCurrent"],
    "equity": ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
    "retained_earnings": ["RetainedEarningsAccumulatedDeficit"],
    # debt building blocks, combined in _total_debt
    "debt_current": ["DebtCurrent"],
    "ltd_current": ["LongTermDebtCurrent", "LongTermDebtAndCapitalLeaseObligationsCurrent"],
    "short_borrowings": ["ShortTermBorrowings"],
    "commercial_paper": ["CommercialPaper"],
    "ltd_noncurrent": ["LongTermDebtNoncurrent", "LongTermDebtAndCapitalLeaseObligations"],
    "debt_combined": ["DebtLongtermAndShorttermCombinedAmount", "DebtInstrumentCarryingAmount"],
    "ltd_total": ["LongTermDebt"],
    "revolver_capacity": ["LineOfCreditFacilityMaximumBorrowingCapacity"],
}
MATURITY_TAGS = [
    "LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths",
    "LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo",
    "LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree",
    "LongTermDebtMaturitiesRepaymentsOfPrincipalInYearFour",
    "LongTermDebtMaturitiesRepaymentsOfPrincipalInYearFive",
    "LongTermDebtMaturitiesRepaymentsOfPrincipalAfterYearFive",
]


@dataclass
class CompanyData:
    ticker: str
    cik: int
    name: str
    asof: str | None
    quarters: pd.DataFrame  # index = quarter end (Timestamp)
    provenance: dict[str, dict[str, str]]  # field -> {period end iso: accession}
    maturities: list[float]  # principal due in years 1..5 and after year 5
    maturities_date: str | None
    notes: list[str] = field(default_factory=list)


def _usd_facts(gaap: dict, tag: str, asof: pd.Timestamp | None) -> pd.DataFrame:
    if tag not in gaap:
        return pd.DataFrame()
    rows = gaap[tag]["units"].get("USD", [])
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = df[df["form"].isin(FORMS)].copy()
    df["end"] = pd.to_datetime(df["end"])
    df["filed"] = pd.to_datetime(df["filed"])
    if "start" in df:
        df["start"] = pd.to_datetime(df["start"])
    if asof is not None:
        df = df[df["filed"] <= asof]
    return df


def _latest(df: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    """Keep the most recently filed fact per period (restatements win, within the vintage)."""
    return df.sort_values("filed").groupby(keys, as_index=False).last()


def duration_quarters(gaap: dict, tag: str, asof: pd.Timestamp | None = None) -> dict:
    """Discrete-quarter values {end: (value, accn)} for one tag, de-cumulating YTD facts."""
    df = _usd_facts(gaap, tag, asof)
    if df.empty or "start" not in df:
        return {}
    df = _latest(df.dropna(subset=["start"]), ["start", "end"])
    df["days"] = (df["end"] - df["start"]).dt.days

    out: dict[pd.Timestamp, tuple[float, str]] = {}
    direct = df[df["days"].between(*QUARTER_DAYS)]
    for r in direct.itertuples():
        out[r.end] = (float(r.val), r.accn)

    # Pairs of cumulative facts sharing a start date: later minus earlier = the quarter in between.
    for _, grp in df[df["days"] > QUARTER_DAYS[1]].groupby("start"):
        grp = pd.concat([grp, direct[direct["start"] == grp["start"].iloc[0]]]).sort_values("end")
        ends, vals, accns = grp["end"].tolist(), grp["val"].tolist(), grp["accn"].tolist()
        for i in range(1, len(ends)):
            gap = (ends[i] - ends[i - 1]).days
            if QUARTER_DAYS[0] <= gap <= QUARTER_DAYS[1] and ends[i] not in out:
                out[ends[i]] = (float(vals[i] - vals[i - 1]), accns[i])
    return out


def instant_values(gaap: dict, tag: str, asof: pd.Timestamp | None = None) -> dict:
    df = _usd_facts(gaap, tag, asof)
    if df.empty:
        return {}
    df = _latest(df, ["end"])
    return {r.end: (float(r.val), r.accn) for r in df.itertuples()}


def _merge_tags(gaap: dict, tags: list[str], extractor, asof) -> dict:
    merged: dict = {}
    for tag in tags:
        for end, v in extractor(gaap, tag, asof).items():
            merged.setdefault(end, v)
    return merged


def _align(series: dict, spine: list[pd.Timestamp]) -> tuple[list[float], dict[str, str]]:
    """Snap {end: (val, accn)} onto the spine of quarter ends (52/53-week calendars drift a few days)."""
    if not series:
        return [np.nan] * len(spine), {}
    ends = np.array(sorted(series), dtype="datetime64[ns]")
    vals, prov = [], {}
    for q in spine:
        diffs = np.abs((ends - np.datetime64(q)).astype("timedelta64[D]").astype(int))
        i = int(np.argmin(diffs))
        if diffs[i] <= ALIGN_TOLERANCE_DAYS:
            v, accn = series[pd.Timestamp(ends[i])]
            vals.append(v)
            prov[q.date().isoformat()] = accn
        else:
            vals.append(np.nan)
    return vals, prov


def _total_debt(q: pd.DataFrame) -> pd.Series:
    """Combine heterogeneous debt tags into one total-debt series, preferring explicit splits."""
    current = q["debt_current"].copy()
    parts = q[["ltd_current", "short_borrowings", "commercial_paper"]]
    current = current.fillna(parts.sum(axis=1, min_count=1)).fillna(0.0)
    split = current + q["ltd_noncurrent"]
    total = split.fillna(q["debt_combined"]).fillna(
        q["ltd_total"] + q[["short_borrowings", "commercial_paper"]].sum(axis=1)
    )
    return total.fillna(0.0)


def season_of(end: pd.Timestamp) -> int:
    """Fiscal-calendar-agnostic season key 0..3 (shift back 10 days so 52/53-week ends land correctly)."""
    return ((end - pd.Timedelta(days=10)).month - 1) // 3


def load_company(ticker: str, asof: str | None = None, min_year: int = 2010) -> CompanyData:
    cik, name = ticker_to_cik(ticker)
    raw = company_facts(cik)
    gaap = raw["facts"].get("us-gaap", {})
    cut = pd.Timestamp(asof) if asof else None

    dur = {k: _merge_tags(gaap, tags, duration_quarters, cut) for k, tags in DURATION.items()}
    inst = {k: _merge_tags(gaap, tags, instant_values, cut) for k, tags in INSTANT.items()}

    spine = sorted(e for e in dur["revenue"] if e.year >= min_year)
    # Drop spine points closer than ~2 months to the previous one (duplicate quarter definitions).
    clean: list[pd.Timestamp] = []
    for e in spine:
        if not clean or (e - clean[-1]).days >= 60:
            clean.append(e)
    spine = clean

    data, provenance = {}, {}
    for k, s in {**dur, **inst}.items():
        data[k], provenance[k] = _align(s, spine)
    q = pd.DataFrame(data, index=pd.DatetimeIndex(spine, name="end"))

    notes = []
    for k in ["dividends", "buybacks", "sbc", "short_investments", "receivables", "inventory", "revolver_capacity"]:
        if q[k].isna().all():
            notes.append(f"{k}: no data, assumed 0")
    # Some filers never tag operating income; rebuild it as pre-tax income plus interest expense.
    if q["operating_income"].isna().any():
        rebuilt = q["pretax_income"] + q["interest_expense"].fillna(0)
        if q["operating_income"].isna().all():
            notes.append("operating income rebuilt as pre-tax income + interest expense")
        q["operating_income"] = q["operating_income"].fillna(rebuilt)
    # Adjusted operating income: add back non-cash impairments. Tags overlap (a cash-flow total vs. its components),
    # so take the largest of the alternative measurements per quarter rather than summing them.
    parts = q[["imp_goodwill", "imp_intangible", "imp_longlived"]].fillna(0).sum(axis=1)
    impairment = (
        pd.concat([q["imp_total"].fillna(0), q["imp_gw_intang"].fillna(0), parts], axis=1).max(axis=1).clip(lower=0)
    )
    q["impairment"] = impairment
    q["operating_income_reported"] = q["operating_income"]
    q["operating_income"] = q["operating_income"] + impairment
    if impairment.gt(0).any():
        notes.append(f"operating income adjusted for impairments in {int(impairment.gt(0).sum())} quarters")
    if q["payables"].isna().all():
        notes.append("payables: no data, assumed 0")
    zero_fill = [
        "dividends",
        "buybacks",
        "sbc",
        "short_investments",
        "receivables",
        "inventory",
        "deferred_revenue",
    ]
    q[zero_fill] = q[zero_fill].fillna(0.0)
    # Balances are sticky: carry the last known value across occasional gaps.
    for k in [
        "cash",
        "ppe",
        "assets",
        "current_assets",
        "current_liabilities",
        "equity",
        "retained_earnings",
        "ltd_noncurrent",
        "debt_combined",
        "ltd_total",
        "payables",
        "revolver_capacity",
    ]:
        q[k] = q[k].ffill(limit=2)
    q["payables"] = q["payables"].fillna(0.0)
    # Debt components stay NaN until the total is assembled: an untagged DebtCurrent must fall back to its
    # parts (LongTermDebtCurrent, commercial paper, short-term borrowings), not count as zero.
    q["total_debt"] = _total_debt(q)
    debt_parts = ["debt_current", "ltd_current", "short_borrowings", "commercial_paper"]
    q[debt_parts] = q[debt_parts].fillna(0.0)
    if q["liabilities"].isna().any():
        derived = q["assets"] - q["equity"]
        if q["liabilities"].isna().all():
            notes.append("liabilities derived as assets - equity")
        q["liabilities"] = q["liabilities"].fillna(derived)
    q["season"] = [season_of(e) for e in q.index]

    maturities, mat_date = _maturity_ladder(gaap, cut)
    return CompanyData(ticker.upper(), cik, name, asof, q, provenance, maturities, mat_date, notes)


def _maturity_ladder(gaap: dict, asof) -> tuple[list[float], str | None]:
    per_tag = [instant_values(gaap, t, asof) for t in MATURITY_TAGS]
    dates = set().union(*[set(d) for d in per_tag[:3]])
    if not dates:
        return [], None
    latest = max(dates)
    ladder = []
    for d in per_tag:
        near = [e for e in d if abs((e - latest).days) <= ALIGN_TOLERANCE_DAYS]
        ladder.append(d[near[0]][0] if near else 0.0)
    return ladder, latest.date().isoformat()
