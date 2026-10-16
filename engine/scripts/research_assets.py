"""Tables, figures and LaTeX macros for the paper's evaluation, generated from docs/paper/research.json.

    uv run python scripts/research_assets.py [path/to/research.json]

Nothing in the evaluation section of the paper is typed by hand: every number comes from this script.
"""

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
PAPER = ROOT / "docs" / "paper"
FIG, TAB = PAPER / "figures", PAPER / "tables"
FIG.mkdir(parents=True, exist_ok=True)
TAB.mkdir(parents=True, exist_ok=True)
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else PAPER / "research.json"
R = json.loads(SRC.read_text(encoding="utf-8"))

BLUE, ORANGE, INK, MUTED, GRID = "#2a78d6", "#eb6834", "#0b0b0b", "#898781", "#e1e0d9"
plt.rcParams.update({
    "font.family": "serif", "font.size": 8.5, "axes.edgecolor": "#9a998f", "axes.linewidth": 0.7,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.5, "axes.axisbelow": True,
    "axes.spines.top": False, "axes.spines.right": False, "xtick.color": "#52514e", "ytick.color": "#52514e",
    "axes.labelcolor": "#2b2a27", "figure.dpi": 200, "savefig.bbox": "tight", "legend.frameon": False,
})

macros: dict[str, str] = {}
LETTERS = "ABCDEFGHIJ"


def m(name: str, value) -> None:
    assert name.isalpha(), name
    macros[name] = str(value)


def f2(x):
    return "--" if x is None or not np.isfinite(x) else f"{x:.2f}"


def f3(x):
    return "--" if x is None or not np.isfinite(x) else f"{x:.3f}"


def pv(p):
    """p-value with its relation for running text: $p\\CovRegP$ renders as p = 0.019 or p < 0.001."""
    if p is None or not np.isfinite(p):
        return "=\\text{--}"
    return "<0.001" if p < 0.001 else f"={p:.3f}"


def pc(x, d=0):
    return f"{x * 100:.{d}f}\\%"


def sp(x, d=0):
    """Signed percentage with a typographic minus."""
    return ("$-$" if x < 0 else "") + pc(abs(x), d)


def lower(name):
    return name if name.split()[0] in ("Altman", "Ohlson", "Zmijewski") else name[0].lower() + name[1:]


def stars(p):
    return "" if p is None else ("$^{***}$" if p < 0.01 else "$^{**}$" if p < 0.05 else "$^{*}$" if p < 0.1 else "")


def table(name: str, body: str) -> None:
    (TAB / f"{name}.tex").write_text(body, encoding="utf-8")


C, BK, P, FC = R["covid"], R["bankruptcy"], R["panel"], R["forecasts"]
ORDER = ["twin", "twin_pb", "altman_z2", "ohlson_o", "zmijewski", "icr", "nd_ebitda", "cash_rev", "current_ratio",
         "static_stress", "rev_vol", "fixed_share", "size"]
NAMES = {
    "twin": "Twin: stress health score", "twin_pb": "Twin: breach probability", "twin_base": "Twin: baseline health",
    "twin_rec": "Twin: recession health", "twin_no_loops": "Twin without feedback loops",
    "altman_z2": "Altman Z$''$", "ohlson_o": "Ohlson O-score", "zmijewski": "Zmijewski score", "icr": "Interest coverage",
    "nd_ebitda": "Net debt / EBITDA", "cash_rev": "Cash / revenue", "current_ratio": "Current ratio",
    "static_stress": "Static stress test", "rev_vol": "Revenue volatility", "fixed_share": "Fixed-cost share",
    "size": "Size (log revenue)",
}

# ------------------------------------------------------------------ COVID cross-section
cp = C["predictors"]
m("CovN", C["n"])
m("CovSevere", C["n_severe"])
m("CovRho", f2(cp["twin"]["rho"]))
m("CovRhoLo", f2(cp["twin"]["rho_ci"][0]))
m("CovRhoHi", f2(cp["twin"]["rho_ci"][1]))
m("CovWithin", f2(cp["twin"]["rho_within_sector"]))
m("CovWithinLo", f2(C["within_sector_ci_twin"][0]))
m("CovWithinHi", f2(C["within_sector_ci_twin"][1]))
m("CovAuc", f2(cp["twin"]["auc_severe"]))
bench = [k for k in ORDER if k not in ("twin", "twin_pb")]
best = max(bench, key=lambda k: cp[k]["rho"])
m("CovBestName", lower(NAMES[best]))
m("CovBestRho", f2(cp[best]["rho"]))
m("CovBestDiff", f2(cp[best]["twin_minus"]["diff"]))
m("CovBestP", pv(cp[best]["twin_minus"]["p"]))
m("CovStaticRho", f2(cp["static_stress"]["rho"]))
m("CovStaticDiff", f2(cp["static_stress"]["twin_minus"]["diff"]))
m("CovStaticP", pv(cp["static_stress"]["twin_minus"]["p"]))
m("CovAltmanAuc", f2(cp["altman_z2"]["auc_severe"]))
m("CovIcrAuc", f2(cp["icr"]["auc_severe"]))
q = C["quintiles"]["severe_share"]
m("CovQFragile", pc(q[-1]))
m("CovQRobust", pc(q[0]))
m("CovQAltmanFragile", pc(C["quintiles_altman"]["severe_share"][-1]))
rg = C["regression"]
m("CovRegT", f"{rg['t']['twin']:.2f}")
m("CovRegP", pv(rg["p"]["twin"]))
m("CovRegRtwo", f2(rg["r2_full"]))
m("CovRegRtwoNo", f2(rg["r2_without_twin"]))
ex = C["exposure"]
m("CovHitRho", f2(ex["rho_hit"]))
m("CovSparedRho", f2(ex["rho_spared"]))
m("CovMedDrop", f"{abs(ex['median_rev_drop']):.0f}\\%")
m("CovSectorAdj", f2(C["sector_adjusted_rho"]))
sm = C["stress_minus_baseline"]
m("CovStressBase", f2(sm["diff"]))
m("CovStressBaseP", pv(sm["p"]))
m("CovBaseRho", f2(C["by_scenario"]["base"]))
dc = C["dividend_cut"]
m("CovDivN", dc["n_payers"])
m("CovDivCuts", dc["n_cuts"])
m("CovDivAuc", f2(dc["auc"]["twin"]))
m("CovDivAltman", f2(dc["auc"]["altman_z2"]))

rows = []
for k in ORDER:
    v = cp[k]
    tm = v["twin_minus"]
    diff = "" if tm is None else f"{tm['diff']:+.2f}{stars(tm['p'])}"
    rows.append(f"{NAMES[k]} & {v['n']} & {f2(v['rho'])} & [{f2(v['rho_ci'][0])}, {f2(v['rho_ci'][1])}] & "
                f"{f2(v['rho_within_sector'])} & {f2(v['auc_severe'])} & {diff} \\\\")
    if k == "twin_pb":
        rows.append("\\addlinespace")
table("covid_predictors", "\n".join([
    "\\begin{tabular}{lrrcrrr}", "\\toprule",
    " & $n$ & $\\rho$ & 95\\% CI & $\\rho$ within sector & AUC (severe) & Twin $-$ predictor \\\\", "\\midrule",
    *rows, "\\bottomrule", "\\end{tabular}"]))

rows = []
for k in ["twin", *bench]:
    rows.append(f"{NAMES[k]} & {rg['coef'][k]:.3f} & ({rg['t'][k]:.2f}){stars(rg['p'][k])} \\\\")
table("covid_regression", "\n".join([
    "\\begin{tabular}{lrr}", "\\toprule", "Percentile rank of & Coefficient & ($t$, HC3) \\\\", "\\midrule", *rows,
    "\\midrule", f"Sector fixed effects & \\multicolumn{{2}}{{r}}{{Yes}} \\\\",
    f"$R^2$ (without the twin) & \\multicolumn{{2}}{{r}}{{{f2(rg['r2_full'])} ({f2(rg['r2_without_twin'])})}} \\\\",
    f"Observations & \\multicolumn{{2}}{{r}}{{{rg['n']}}} \\\\", "\\bottomrule", "\\end{tabular}"]))

# ------------------------------------------------------------------ loops and scenarios
ab, abpb = C["ablations"], C["ablations_pb_loss"]
h12 = C.get("ablations_h12", {})
LOOP = {"full": "All loops (full twin)", "no_r1": "without R1 (spread spiral)", "no_r2": "without R2 (market-access cliff)",
        "no_b1": "without B1 (cash conservation)", "no_b2": "without B2 (restructuring)", "no_loops": "without any loop"}
def loss(d):
    return "" if d is None else f"{d['diff']:+.3f}{stars(d['p'])}"


rows = []
for k in LOOP:
    e12 = h12.get(k, {})
    rows.append(
        f"{LOOP[k]} & {f3(ab[k]['rho'])} & {loss(ab[k]['loss'])} & {f3(ab[k]['rho_pb'])} & {loss(abpb.get(k))} & "
        f"{f3(e12.get('rho'))} & {loss(e12.get('loss'))} & {f3(e12.get('rho_pb'))} & {loss(e12.get('loss_pb'))} \\\\"
    )
table("ablations", "\n".join([
    "\\begin{tabular}{lrrrrrrrr}", "\\toprule",
    " & \\multicolumn{4}{c}{8 quarters} & \\multicolumn{4}{c}{12 quarters} \\\\",
    "\\cmidrule(lr){2-5}\\cmidrule(lr){6-9}",
    " & $\\rho$(health) & loss & $\\rho$(breach) & loss & $\\rho$(health) & loss & $\\rho$(breach) & loss \\\\",
    "\\midrule", *rows, "\\bottomrule", "\\end{tabular}"]))
m("AblHealthLoss", f3(ab["no_loops"]["loss"]["diff"]))
m("AblHealthP", pv(ab["no_loops"]["loss"]["p"]))
m("AblPbFull", f2(ab["full"]["rho_pb"]))
m("AblPbNoLoops", f2(ab["no_loops"]["rho_pb"]))
m("AblPbLoss", f2(abpb["no_loops"]["diff"]))
m("AblPbLossP", pv(abpb["no_loops"]["p"]))
m("AblRtwoLoss", f2(abpb["no_r2"]["diff"]))
m("AblRtwoLossLo", f2(abpb["no_r2"]["ci"][0]))
m("AblRtwoLossHi", f2(abpb["no_r2"]["ci"][1]))
m("AblRtwoP", pv(abpb["no_r2"]["p"]))
if h12:
    m("AblTwelvePbLoss", f2(h12["no_loops"]["loss_pb"]["diff"]))
    m("AblTwelvePbP", pv(h12["no_loops"]["loss_pb"]["p"]))
    m("AblTwelveHealthLoss", f3(h12["no_loops"]["loss"]["diff"]))
    m("AblTwelveHealthP", pv(h12["no_loops"]["loss"]["p"]))
    m("AblTwelveRtwoLoss", f2(h12["no_r2"]["loss_pb"]["diff"]))
    m("AblTwelveRtwoP", pv(h12["no_r2"]["loss_pb"]["p"]))

SCN = {"base": "Baseline", "rates_200": "Rates +200bp", "sales_20": "Sales $-$20\\%", "recession": "Recession",
       "credit_crunch": "Credit crunch", "pandemic": "Demand freeze"}
table("scenarios", "\n".join([
    "\\begin{tabular}{" + "l" + "r" * len(SCN) + "}", "\\toprule", " & " + " & ".join(SCN.values()) + " \\\\", "\\midrule",
    "$\\rho$ with realized burn & " + " & ".join(f2(C["by_scenario"][k]) for k in SCN) + " \\\\",
    "\\bottomrule", "\\end{tabular}"]))

# ------------------------------------------------------------------ 2020 bankruptcies
bp = BK["predictors"]
m("BkN", BK["n_bankrupt"])
m("BkSurv", BK["n_survivors"])
m("BkAuc", f2(bp["twin"]["auc"]))
m("BkAucBase", f2(bp["twin_base"]["auc"]))
m("BkAucLo", f2(bp["twin"]["auc_ci"][0]))
m("BkAucHi", f2(bp["twin"]["auc_ci"][1]))
m("BkAltman", f2(bp["altman_z2"]["auc"]))
m("BkAltmanP", pv(bp["altman_z2"]["twin_minus"]["p"]))
m("BkOhlson", f2(bp["ohlson_o"]["auc"]))
m("BkSize", f2(bp["size"]["auc"]))
m("BkDecile", pc(BK["share_in_most_fragile_decile"]))
m("BkQuintile", pc(BK["share_in_most_fragile_quintile"]))
sz = BK["size_matched"]
m("BkSmSurv", sz["n_survivors"])
m("BkSmBk", sz["n_bankrupt"])
m("BkSmTwin", f2(sz["auc"]["twin"]))
m("BkSmTwinBase", f2(sz["auc"]["twin_base"]))
m("BkSmAltman", f2(sz["auc"]["altman_z2"]))
m("BkSmSize", f2(sz["auc"]["size"]))
lw = BK["logit_with_size"]
m("BkLogitZ", f"{lw['twin']['z']:.2f}")
m("BkLogitP", pv(lw["twin"]["p"]))
m("BkLogitAltmanZ", f"{lw['altman_z2']['z']:.2f}")
ms = BK["sector_matched"]
m("BkSecTwin", f2(ms["auc_twin"]))
m("BkSecAltman", f2(ms["auc_altman"]))
m("BkSecN", ms["n"])
rows = []
for k in ["twin", "twin_base", "twin_pb", *bench]:
    v = bp[k]
    tm = v["twin_minus"]
    diff = "" if tm is None else f"{tm['diff']:+.2f}{stars(tm['p'])}"
    smv = sz["auc"].get(k)
    rows.append(f"{NAMES[k]} & {v['n_bankrupt']} & {f2(v['auc'])} & [{f2(v['auc_ci'][0])}, {f2(v['auc_ci'][1])}] & "
                f"{diff} & {f2(smv) if smv is not None else ''} \\\\")
    if k == "twin_pb":
        rows.append("\\addlinespace")
table("bankruptcy", "\n".join([
    "\\begin{tabular}{lrrcrr}", "\\toprule",
    " & Bankrupt firms & AUC & 95\\% CI & Stress twin $-$ predictor & AUC, size-matched \\\\", "\\midrule",
    *rows, "\\bottomrule", "\\end{tabular}"]))
firms = sorted(BK["firms"], key=lambda r: r["h_pandemic"])
pct_rank = sorted(BK["percentile_in_sp500"])
bk_csv = {r["key"]: r for r in __import__("csv").DictReader(open(ROOT / "engine" / "fintwin" / "data" / "bankruptcies_2020.csv", encoding="utf-8"))}
rows = []
for r in firms:
    meta = bk_csv.get(r["ticker"], {})
    rows.append(f"{meta.get('name', r['name']).replace('&', '\\&')} & {r['sector']} & {meta.get('chapter11', '')} & "
                f"{r['h_pandemic']:.1f} & {r['h_base']:.1f} \\\\")
table("bankrupt_firms", "\n".join([
    "\\begin{tabular}{llcrr}", "\\toprule", "Company & Sector & Chapter 11 & Stress health & Baseline health \\\\",
    "\\midrule", *rows, "\\bottomrule", "\\end{tabular}"]))

# ------------------------------------------------------------------ panel 2013-2023
m("PanFirmYears", f"{P['n_firm_years']:,}".replace(",", "{,}"))
m("PanFirms", P["n_firms"])
EV = {"severe_burn": "Severe cash burn", "coverage_collapse": "Coverage collapse", "dividend_cut": "Dividend cut"}
rows = []
for ev, label in EV.items():
    e = P[ev]
    uni = e["univariate"]
    bb = max((k for k in bench if k in uni), key=lambda k: uni[k]["auc"])
    o = e["out_of_sample"]
    d = o["delta_auc_twin_added"]
    lg = e["clustered_logit"]["twin"]
    rows.append(
        f"{label} & {e['n']:,} & {e['events']} & {f2(uni['twin']['auc'])} & {f2(uni[bb]['auc'])} ({NAMES[bb]}) & "
        f"{f2(o['benchmarks']['auc'])} & {f2(o['benchmarks_plus_twin']['auc'])} & {d['diff']:+.3f} [{d['ci'][0]:+.3f}, {d['ci'][1]:+.3f}]{stars(d['p'])} & "
        f"{lg['z']:.2f} \\\\".replace(",", "{,}", 1)
    )
table("panel", "\n".join([
    "\\resizebox{\\linewidth}{!}{%",
    "\\begin{tabular}{lrrrlrrlr}", "\\toprule",
    " & & & \\multicolumn{2}{c}{Univariate AUC} & \\multicolumn{3}{c}{Out-of-sample logit AUC} & Twin \\\\",
    "\\cmidrule(lr){4-5}\\cmidrule(lr){6-8}",
    "Event (next 8 quarters) & Firm-years & Events & Twin & Best benchmark & Benchmarks & + Twin & $\\Delta$ [95\\% CI] & $z$ \\\\",
    "\\midrule", *rows, "\\bottomrule", "\\end{tabular}}"]))
sb = P["severe_burn"]
m("PanEvents", sb["events"])
m("PanRate", pc(sb["base_rate"], 1))
m("PanTwinAuc", f2(sb["univariate"]["twin"]["auc"]))
m("PanTwinAucLo", f2(sb["univariate"]["twin"]["auc_ci"][0]))
m("PanTwinAucHi", f2(sb["univariate"]["twin"]["auc_ci"][1]))
pb_best = max(bench, key=lambda k: sb["univariate"][k]["auc"])
m("PanBestName", lower(NAMES[pb_best]))
m("PanBestAuc", f2(sb["univariate"][pb_best]["auc"]))
m("PanBestDiffP", pv(sb["univariate"][pb_best]["twin_minus"]["p"]))
m("PanBestDiff", f2(sb["univariate"][pb_best]["twin_minus"]["diff"]))
o = sb["out_of_sample"]
m("PanOosBench", f2(o["benchmarks"]["auc"]))
m("PanOosPlus", f2(o["benchmarks_plus_twin"]["auc"]))
m("PanOosTwin", f2(o["twin_only"]["auc"]))
m("PanOosDelta", f"{o['delta_auc_twin_added']['diff']:.3f}")
m("PanOosDeltaLo", f"{o['delta_auc_twin_added']['ci'][0]:.3f}")
m("PanOosDeltaHi", f"{o['delta_auc_twin_added']['ci'][1]:.3f}")
m("PanOosN", f"{o['n_test']:,}".replace(",", "{,}"))
m("PanOosYears", f"{o['test_years'][0]}--{o['test_years'][-1]}")
m("PanBrierBench", f3(o["benchmarks"]["brier"]))
m("PanBrierPlus", f3(o["benchmarks_plus_twin"]["brier"]))
m("PanLogitZ", f"{sb['clustered_logit']['twin']['z']:.2f}")
nl = sb["univariate"].get("twin_no_loops")
m("PanNoLoopsAuc", f2(nl["auc"]) if nl else "--")
m("PanCovTwin", f2(P["coverage_collapse"]["univariate"]["twin"]["auc"]))
m("PanCovIcr", f2(P["coverage_collapse"]["univariate"]["icr"]["auc"]))
m("PanCovDelta", f"{P['coverage_collapse']['out_of_sample']['delta_auc_twin_added']['diff']:+.3f}")
m("PanDivTwin", f2(P["dividend_cut"]["univariate"]["twin"]["auc"]))
m("PanDivDelta", f"{P['dividend_cut']['out_of_sample']['delta_auc_twin_added']['diff']:+.3f}")

# ------------------------------------------------------------------ forecasts
rows = []
for var, label in (("revenue", "Revenue"), ("cash_like", "Cash and short-term investments")):
    v = FC[var]
    cells = []
    for b in ("rw", "ets"):
        x = v[b]
        cells.append(f"{x['skill_scaled'] * 100:+.0f}\\% & {x['skill_pooled'] * 100:+.0f}\\% & {pc(x['share_better'])} & {x['dm_t']:.1f}")
    rows.append(f"{label} & {v['n']:,} & {v['n_firms']} & ".replace(",", "{,}", 1) + " & ".join(cells) + " \\\\")
table("forecasts", "\n".join([
    "\\begin{tabular}{lrrrrrrrrrr}", "\\toprule",
    " & & & \\multicolumn{4}{c}{vs.\\ seasonal random walk} & \\multicolumn{4}{c}{vs.\\ ETS} \\\\",
    "\\cmidrule(lr){4-7}\\cmidrule(lr){8-11}",
    " & Forecasts & Firms & Skill & Pooled & Better & DM $t$ & Skill & Pooled & Better & DM $t$ \\\\",
    "\\midrule", *rows, "\\bottomrule", "\\end{tabular}"]))
fr, fcash = FC["revenue"], FC["cash_like"]
m("FcRevN", f"{fr['n']:,}".replace(",", "{,}"))
m("FcRevRw", sp(fr["rw"]["skill_scaled"]))
m("FcRevEts", sp(fr["ets"]["skill_scaled"]))
m("FcRevEtsT", f"{fr['ets']['dm_t']:.1f}")
m("FcRevRwT", f"{fr['rw']['dm_t']:.1f}")
m("FcCashRw", sp(fcash["rw"]["skill_scaled"]))
m("FcCashEts", sp(fcash["ets"]["skill_scaled"]))
m("FcEtsVsRwRev", sp(fr["ets_vs_rw_skill_scaled"]))

# ------------------------------------------------------------------ figures
rows_c = [r for r in C["rows"] if r["real_burn"] is not None]
h = np.array([r["h_pandemic"] for r in rows_c])
burn = np.array([r["real_burn"] for r in rows_c])
fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.0, 2.7), gridspec_kw={"width_ratios": [1.35, 1]})
a1.scatter(h, np.clip(burn, -80, 40), s=7, color=BLUE, alpha=0.55, lw=0)
for r in rows_c:
    off = {"CCL": (10, 6), "RCL": (12, -1), "NCLH": (10, -9), "BA": (8, 2), "WMT": (-6, 9), "AAPL": (4, 6)}
    if r["ticker"] in off:
        a1.annotate(r["ticker"], (r["h_pandemic"], max(r["real_burn"], -80)), fontsize=6.5, color=INK,
                    xytext=off[r["ticker"]], textcoords="offset points",
                    arrowprops={"arrowstyle": "-", "lw": 0.4, "color": MUTED})
a1.axhline(-10, color=ORANGE, lw=0.8, ls="--")
a1.text(98, -9, "severe burn", color=ORANGE, fontsize=6.5, ha="right", va="bottom")
a1.set_xlabel("Twin stress health score, frozen 20 Feb 2020")
a1.set_ylabel("Worst cumulative FCF 2020-21\n(% of 2019 revenue, clipped)")
xq = np.arange(5)
a2.bar(xq - 0.19, np.array(C["quintiles"]["severe_share"][::-1]) * 100, 0.38, color=BLUE, label="Twin stress score")
a2.bar(xq + 0.19, np.array(C["quintiles_altman"]["severe_share"][::-1]) * 100, 0.38, color="#b9b8ad", label="Altman Z$''$")
a2.set_xticks(xq, ["most\nfragile", "2", "3", "4", "most\nrobust"])
a2.set_ylabel("Severe cash burn (% of quintile)")
a2.legend(fontsize=7, loc="upper right")
fig.tight_layout()
fig.savefig(FIG / "covid.pdf")
plt.close(fig)

fig, ax = plt.subplots(figsize=(7.0, 2.5))
by = sb["auc_by_year"]
years = sorted(int(y) for y in by["twin"])
style = {"twin": (BLUE, 2.0, "Twin"), "altman_z2": ("#6e6d66", 1.0, "Altman Z$''$"), "icr": ("#a3a296", 1.0, "Interest coverage"),
         "nd_ebitda": ("#c9c8bd", 1.0, "Net debt / EBITDA"), "static_stress": (ORANGE, 1.0, "Static stress test")}
for k, (col, lw, lab) in style.items():
    ax.plot(years, [by[k][str(y)] if str(y) in by[k] else by[k][y] for y in years], color=col, lw=lw, marker="o", ms=2.5, label=lab)
ax.axhline(0.5, color=MUTED, lw=0.6, ls=":")
ax.set_ylabel("AUC, severe cash burn\nin the next 8 quarters")
ax.set_xlabel("Cutoff (15 February of)")
ax.legend(ncol=5, fontsize=6.8, loc="lower center", bbox_to_anchor=(0.5, 1.0))
fig.tight_layout()
fig.savefig(FIG / "panel_auc.pdf")
plt.close(fig)

fig, ax = plt.subplots(figsize=(7.0, 1.9))
sp_h = h
bk_h = np.array([r["h_pandemic"] for r in BK["firms"]])
bins = np.linspace(0, 100, 26)
ax.hist(sp_h, bins=bins, color="#c9c8bd", label=f"S\\&P 500 non-financials (n={len(sp_h)})", density=True)
ax.hist(bk_h, bins=bins, color=ORANGE, alpha=0.85, label=f"Chapter 11 filers, 2020 (n={len(bk_h)})", density=True)
ax.set_xlabel("Twin stress health score, frozen 20 Feb 2020")
ax.set_yticks([])
ax.legend(fontsize=7)
fig.tight_layout()
fig.savefig(FIG / "bankrupt.pdf")
plt.close(fig)

(PAPER / "research_numbers.tex").write_text(
    "% generated by engine/scripts/research_assets.py from research.json\n"
    + "\n".join(f"\\newcommand{{\\{k}}}{{{v}}}" for k, v in sorted(macros.items())) + "\n",
    encoding="utf-8",
)
print(f"{len(macros)} macros, {len(list(TAB.glob('*.tex')))} tables -> {PAPER}")
