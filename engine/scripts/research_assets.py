"""Tables, figures and LaTeX macros for the paper's evaluation, generated from docs/paper/research.json.

    uv run python scripts/research_assets.py [path/to/research.json]

Nothing in the evaluation section of the paper is typed by hand: every number comes from this script.
"""

import csv
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


def m(name: str, value) -> None:
    assert name.isalpha(), name
    macros[name] = str(value)


def ok(x) -> bool:
    return x is not None and np.isfinite(x)


def f2(x):
    return f"{x:.2f}".replace("-", "$-$") if ok(x) else "--"


def f3(x):
    return f"{x:.3f}".replace("-", "$-$") if ok(x) else "--"


def sgn(x, d=2):
    return (f"{x:+.{d}f}".replace("-", "$-$")) if ok(x) else "--"


def pv(p):
    """p-value with its relation, for running text: $p\\Macro$ renders as p = 0.019 or p < 0.001."""
    if not ok(p):
        return "=\\text{--}"
    return "<0.001" if p < 0.001 else f"={p:.3f}"


def pc(x, d=0):
    return f"{x * 100:.{d}f}\\%"


def sp(x, d=0):
    """Signed percentage with a typographic minus."""
    return ("$-$" if x < 0 else "") + pc(abs(x), d)


def stars(p):
    return "" if not ok(p) else ("$^{***}$" if p < 0.01 else "$^{**}$" if p < 0.05 else "$^{*}$" if p < 0.1 else "")


def diff(d, digits=2):
    return "" if not d else f"{sgn(d['diff'], digits)}{stars(d['p'])}"


def ci_txt(c):
    return f"[{f2(c[0])}, {f2(c[1])}]"


def big(n):
    return f"{n:,}".replace(",", "{,}")


def table(name: str, lines: list[str]) -> None:
    (TAB / f"{name}.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")


C, CA, BK, P, FC, S = (R[k] for k in ("covid", "covid_abnormal", "bankruptcy", "panel", "forecasts", "structural"))
NAMES = {
    "twin": "Twin: stress health score", "twin_base": "Twin: baseline health score", "twin_pb": "Twin: breach probability",
    "twin_rec": "Twin: recession health score", "twin_no_loops": "Twin without feedback loops",
    "formula": "Health formula, no simulation", "altman_z2": "Altman Z$''$", "ohlson_o": "Ohlson O-score",
    "zmijewski": "Zmijewski score", "icr": "Interest coverage", "nd_ebitda": "Net debt / EBITDA",
    "cash_rev": "Cash / revenue", "current_ratio": "Current ratio", "static_stress": "Static stress test",
    "rev_vol": "Revenue volatility", "fixed_share": "Fixed-cost share", "size": "Size (log revenue)",
    "fcf_margin": "Trailing FCF margin", "capex_rev": "Capex / revenue",
}
CLASSIC = ["altman_z2", "ohlson_o", "zmijewski", "icr", "nd_ebitda", "cash_rev", "current_ratio", "static_stress",
           "rev_vol", "fixed_share", "size"]
CASHFLOW = ["fcf_margin", "capex_rev"]
ORDER = ["twin", "twin_base", "twin_pb", "formula", *CLASSIC, *CASHFLOW]


def lower(name):
    return name if name.split()[0] in ("Altman", "Ohlson", "Zmijewski") else name[0].lower() + name[1:]


m("NBench", len(CLASSIC) + len(CASHFLOW))

# ------------------------------------------------------------------ 1. ranking fragility before COVID
cp, ca = C["predictors"], CA["predictors"]
m("CovN", C["n"])
m("CovSevere", C["n_severe"])
m("CovRho", f2(cp["twin"]["rho"]))
m("CovRhoLo", f2(cp["twin"]["rho_ci"][0]))
m("CovRhoHi", f2(cp["twin"]["rho_ci"][1]))
m("CovWithin", f2(cp["twin"]["rho_within_sector"]))
m("CovWithinLo", f2(C["within_sector_ci_twin"][0]))
m("CovWithinHi", f2(C["within_sector_ci_twin"][1]))
best_classic = max(CLASSIC, key=lambda k: cp[k]["rho"])
m("CovClassicName", lower(NAMES[best_classic]))
m("CovClassicRho", f2(cp[best_classic]["rho"]))
m("CovClassicDiff", f2(cp[best_classic]["twin_minus"]["diff"]))
m("CovClassicP", pv(cp[best_classic]["twin_minus"]["p"]))
m("CovAltmanRho", f2(cp["altman_z2"]["rho"]))
m("CovAltmanDiff", f2(cp["altman_z2"]["twin_minus"]["diff"]))
m("CovAltmanP", pv(cp["altman_z2"]["twin_minus"]["p"]))
m("CovStaticRho", f2(cp["static_stress"]["rho"]))
m("CovStaticP", pv(cp["static_stress"]["twin_minus"]["p"]))
m("CovFormulaRho", f2(cp["formula"]["rho"]))
m("CovFormulaDiff", f2(cp["formula"]["twin_minus"]["diff"]))
m("CovFormulaP", pv(cp["formula"]["twin_minus"]["p"]))
m("CovBaseRho", f2(cp["twin_base"]["rho"]))
m("CovFcfRho", f2(cp["fcf_margin"]["rho"]))
m("CovFcfLo", f2(cp["fcf_margin"]["rho_ci"][0]))
m("CovFcfHi", f2(cp["fcf_margin"]["rho_ci"][1]))
m("CovFcfN", cp["fcf_margin"]["n"])
m("CovFcfDiff", f2(-cp["fcf_margin"]["twin_minus"]["diff"]))
m("CovFcfWithin", f2(cp["fcf_margin"]["rho_within_sector"]))
m("CovCompRho", f2(C["composite"]["rho"]))
rg = C["regression"]
m("CovRegT", f2(rg["t"]["twin"]))
m("CovRegP", pv(rg["p"]["twin"]))
m("CovRegFcfT", f2(rg["t"]["fcf_margin"]))
m("CovRegRtwo", f2(rg["r2_full"]))
m("CovRegRtwoNo", f2(rg["r2_without_twin"]))
q = C["quintiles"]
m("CovQFragile", pc(q["severe_share"][-1]))
m("CovQRobust", pc(q["severe_share"][0]))
m("CovQShare", pc(q["top_quintile_share_of_severe"]))
# same paired comparison as the table row, so text and table agree
m("CovStressBase", f2(cp["twin_base"]["twin_minus"]["diff"]))
m("CovStressBaseP", pv(cp["twin_base"]["twin_minus"]["p"]))
m("CovSectorAdj", f2(C["sector_adjusted_rho"]))
m("CovHitRho", f2(C["exposure"]["rho_hit"]))
m("CovSparedRho", f2(C["exposure"]["rho_spared"]))
m("CovMedDrop", f"{abs(C['exposure']['median_rev_drop']):.0f}\\%")
rb = C["robustness"]
m("CovNoAddedRho", f2(rb["without_added_companies"]["rho_twin"]))
m("CovNoUtilRho", f2(rb["without_utilities"]["rho_twin"]))
# abnormal burn
m("AbnN", CA["n"])
m("AbnSevere", CA["n_severe"])
m("AbnTwinRho", f2(ca["twin"]["rho"]))
m("AbnTwinLo", f2(ca["twin"]["rho_ci"][0]))
m("AbnTwinHi", f2(ca["twin"]["rho_ci"][1]))
m("AbnAltmanRho", f2(ca["altman_z2"]["rho"]))
m("AbnFcfRho", f2(ca["fcf_margin"]["rho"]))
m("AbnRevVolRho", f2(ca["rev_vol"]["rho"]))
m("AbnCapexRho", f2(ca["capex_rev"]["rho"]))
m("AbnFixedRho", f2(ca["fixed_share"]["rho"]))
m("AbnCompRho", f2(CA["composite"]["rho"]))
m("AbnCashRho", f2(ca["cash_rev"]["rho"]))
m("AbnCashLo", f2(ca["cash_rev"]["rho_ci"][0]))
m("AbnCashHi", f2(ca["cash_rev"]["rho_ci"][1]))

rows = []
for k in ORDER:
    if k not in cp:
        continue
    v, a = cp[k], ca.get(k, {})
    rows.append(f"{NAMES[k]} & {v['n']} & {f2(v['rho'])} & {ci_txt(v['rho_ci'])} & {f2(v['rho_within_sector'])} & "
                f"{diff(v['twin_minus'])} & {f2(a.get('rho'))} & {ci_txt(a['rho_ci']) if a else ''} \\\\")
    if k in ("formula", "size"):
        rows.append("\\addlinespace")
rows.append("\\addlinespace")
rows.append(f"Cross-validated composite of all benchmarks & {C['n']} & {f2(C['composite']['rho'])} & & & "
            f"{diff(C['composite']['twin_minus'])} & {f2(CA['composite']['rho'])} & \\\\")
table("covid_predictors", [
    "\\begin{tabular}{lrrcrrrc}", "\\toprule",
    " & & \\multicolumn{4}{c}{Raw cash burn} & \\multicolumn{2}{c}{Abnormal cash burn} \\\\",
    "\\cmidrule(lr){3-6}\\cmidrule(lr){7-8}",
    " & $n$ & $\\rho$ & 95\\% CI & Within sector & Twin $-$ predictor & $\\rho$ & 95\\% CI \\\\", "\\midrule",
    *rows, "\\bottomrule", "\\end{tabular}"])

rows = [f"{NAMES.get(k, k)} & {rg['coef'][k]:.3f}".replace("-", "$-$") + f" & ({f2(rg['t'][k])}){stars(rg['p'][k])} \\\\"
        for k in rg["coef"]]
table("covid_regression", [
    "\\begin{tabular}{lrr}", "\\toprule", "Percentile rank of & Coefficient & ($t$, HC3) \\\\", "\\midrule", *rows,
    "\\midrule", "Sector fixed effects & \\multicolumn{2}{r}{Yes} \\\\",
    f"$R^2$ (without the twin) & \\multicolumn{{2}}{{r}}{{{f2(rg['r2_full'])} ({f2(rg['r2_without_twin'])})}} \\\\",
    f"Observations & \\multicolumn{{2}}{{r}}{{{rg['n']}}} \\\\", "\\bottomrule", "\\end{tabular}"])

# ------------------------------------------------------------------ 2. bankruptcies
bp, sz = BK["predictors"], BK["size_matched"]
m("BkN", BK["n_bankrupt"])
m("BkSurv", BK["n_survivors"])
m("BkSmSurv", sz["n_survivors"])
m("BkSmBk", sz["n_bankrupt"])
for key, mac in (("twin", "BkSmTwin"), ("twin_base", "BkSmBase"), ("altman_z2", "BkSmAltman"), ("formula", "BkSmFormula"),
                 ("fcf_margin", "BkSmFcf"), ("size", "BkSmSize"), ("icr", "BkSmIcr")):
    m(mac, f2(sz["auc"][key]))
m("BkSmTwinLo", f2(sz["auc_ci"]["twin"][0]))
m("BkSmTwinHi", f2(sz["auc_ci"]["twin"][1]))
pr = sz["paired"]
m("BkSmTwinAltmanDiff", f2(pr["twin_minus_altman_z2"]["diff"]))
m("BkSmTwinAltmanP", pv(pr["twin_minus_altman_z2"]["p"]))
m("BkSmTwinFormulaDiff", sgn(pr["twin_minus_formula"]["diff"], 3))
m("BkSmTwinFormulaP", pv(pr["twin_minus_formula"]["p"]))
m("BkSmBaseFormulaP", pv(pr["twin_base_minus_formula"]["p"]))
m("BkSmTwinFcfDiff", sgn(pr["twin_minus_fcf_margin"]["diff"]))
m("BkSmTwinFcfP", pv(pr["twin_minus_fcf_margin"]["p"]))
m("BkSmTwinIcrP", pv(pr["twin_minus_icr"]["p"]))
m("BkAuc", f2(bp["twin"]["auc"]))
m("BkAucBase", f2(bp["twin_base"]["auc"]))
m("BkSize", f2(bp["size"]["auc"]))
m("BkStressBase", sgn(bp["twin_base"]["twin_minus"]["diff"]))
m("BkStressBaseP", pv(bp["twin_base"]["twin_minus"]["p"]))
m("BkSmFcfN", pr["twin_minus_fcf_margin"]["n"])
m("BkFcfBk", bp["fcf_margin"]["n_bankrupt"])
m("BkDecile", pc(BK["share_in_most_fragile_decile"]))
rows = []
for k in ORDER:
    if k not in bp:
        continue
    v = bp[k]
    rows.append(f"{NAMES[k]} & {v['n_bankrupt']} & {f2(v['auc'])} & {ci_txt(v['auc_ci'])} & {diff(v['twin_minus'])} & "
                f"{f2(sz['auc'].get(k))} \\\\")
    if k in ("formula", "size"):
        rows.append("\\addlinespace")
table("bankruptcy", [
    "\\begin{tabular}{lrrcrr}", "\\toprule",
    " & Bankrupt firms & AUC & 95\\% CI & Twin $-$ predictor & AUC, size-matched \\\\", "\\midrule",
    *rows, "\\bottomrule", "\\end{tabular}"])
bk_csv = {r["key"]: r for r in csv.DictReader(open(ROOT / "engine" / "fintwin" / "data" / "bankruptcies_2020.csv", encoding="utf-8"))}
rows = []
for r in sorted(BK["firms"], key=lambda r: r["h_pandemic"]):
    meta = bk_csv.get(r["ticker"], {})
    name = meta.get("name", r["name"]).replace("&", "\\&")
    rows.append(f"{name} & {r['sector']} & {meta.get('chapter11', '')} & {r['h_pandemic']:.1f} & {r['h_base']:.1f} \\\\")
table("bankrupt_firms", [
    "\\begin{tabular}{llcrr}", "\\toprule", "Company & Sector & Chapter 11 & Stress health & Baseline health \\\\",
    "\\midrule", *rows, "\\bottomrule", "\\end{tabular}"])

# ------------------------------------------------------------------ 3. translating a shock into cash
sc, sp_ = S["covid"], S["panel"]
m("StrCovN", sc["n"])
m("StrCovDownN", sc["revenue_down_10pct"]["n"])
m("StrPanN", big(sp_["n"]))
m("StrPanFirms", sp_["n_firms"])
m("StrPanDownN", sp_["revenue_down_10pct"]["n"])
d = sc["revenue_down_10pct"]
m("StrCovDownCfoTwin", f2(d["cfo"]["rho_twin"]))
m("StrCovDownCfoMargin", f2(d["cfo"]["rho_margin"]))
m("StrCovDownCfoP", pv(d["cfo"]["twin_minus_margin"]["p"]))
m("StrCovDownFcfTwin", f2(d["fcf"]["rho_twin"]))
m("StrCovDownFcfMargin", f2(d["fcf"]["rho_margin"]))
m("StrCovDownFcfP", pv(d["fcf"]["twin_minus_margin"]["p"]))
m("StrCovDownIncr", f2(d["cfo"]["rho_incremental"]))
a = sc["all"]
m("StrCovIncr", f2(a["cfo"]["rho_incremental"]))
m("StrCovIncrLo", f2(a["cfo"]["rho_incremental_ci"][0]))
m("StrCovIncrHi", f2(a["cfo"]["rho_incremental_ci"][1]))
m("StrCovAllCfoTwin", f2(a["cfo"]["rho_twin"]))
m("StrCovAllCfoMargin", f2(a["cfo"]["rho_margin"]))
pa = sp_["all"]
m("StrPanIncr", f2(pa["cfo"]["rho_incremental"]))
m("StrPanIncrLo", f2(pa["cfo"]["rho_incremental_ci"][0]))
m("StrPanIncrHi", f2(pa["cfo"]["rho_incremental_ci"][1]))
m("StrPanCfoTwin", f2(pa["cfo"]["rho_twin"]))
m("StrPanCfoMargin", f2(pa["cfo"]["rho_margin"]))
m("StrPanMaeTwin", f"{pa['cfo']['mae_twin']:.1f}")
m("StrPanMaeMargin", f"{pa['cfo']['mae_margin']:.1f}")
m("StrPanCloser", pc(pa["cfo"]["share_twin_closer"]))
yr_incr = [v["rho_incremental_cfo"] for v in sp_["by_year"].values()]
m("StrPanYearMin", f2(min(yr_incr)))
m("StrPanYearMax", f2(max(yr_incr)))
m("StrPanYearMinYear", min(sp_["by_year"], key=lambda y: sp_["by_year"][y]["rho_incremental_cfo"]))
pdn = sp_["revenue_down_10pct"]
m("StrPanDownIncr", f2(pdn["cfo"]["rho_incremental"]))
m("StrPanDownCfoTwin", f2(pdn["cfo"]["rho_twin"]))
m("StrPanDownCfoMargin", f2(pdn["cfo"]["rho_margin"]))
rows = []
for label, blk in (("2020, all companies", sc["all"]), ("2020, revenue down $>$10\\%", sc["revenue_down_10pct"]),
                   ("2014--2023, all firm-years", sp_["all"]), ("2014--2023, revenue down $>$10\\%", sp_["revenue_down_10pct"])):
    for var, vl in (("cfo", "Operating cash flow"), ("fcf", "Free cash flow")):
        e = blk[var]
        rows.append(f"{label} & {vl} & {big(blk['n'])} & {f2(e['rho_twin'])} & {f2(e['rho_margin'])} & "
                    f"{diff(e['twin_minus_margin'])} & {f2(e['rho_incremental'])} {ci_txt(e['rho_incremental_ci'])} & "
                    f"{e['mae_twin']:.1f} / {e['mae_margin']:.1f} \\\\")
    rows.append("\\addlinespace")
table("structural", [
    "\\begin{tabular}{llrrrrlr}", "\\toprule",
    " & & & \\multicolumn{3}{c}{$\\rho$ with realized cash} & Incremental $\\rho$ & Median abs.\\ error \\\\",
    "\\cmidrule(lr){4-6}",
    "Sample & Cash measure & $n$ & Twin & Margin rule & Difference & [95\\% CI] & twin / rule (pp) \\\\", "\\midrule",
    *rows[:-1], "\\bottomrule", "\\end{tabular}"])

# ------------------------------------------------------------------ 4. distress panel
m("PanFirmYears", big(P["n_firm_years"]))
m("PanFirms", P["n_firms"])
m("PanYears", f"{P['years'][0]}--{P['years'][-1]}")
EV = {"severe_burn": "Severe cash burn", "abnormal_burn": "Severe abnormal burn",
      "coverage_collapse": "Coverage collapse", "dividend_cut": "Dividend cut"}
rows = []
for ev, label in EV.items():
    e = P[ev]
    uni = e["univariate"]
    bb = max((k for k in [*CLASSIC, *CASHFLOW] if k in uni), key=lambda k: uni[k]["auc"])
    o = e["out_of_sample"]
    dd = o["delta_twin_beyond_formula"]
    rows.append(f"{label} & {big(e['n'])} & {e['events']} & {f2(uni['twin']['auc'])} & {f2(uni['formula']['auc'])} & "
                f"{f2(uni[bb]['auc'])} ({lower(NAMES[bb])}) & {f2(o['benchmarks_formula']['auc'])} & "
                f"{f2(o['benchmarks_formula_twin']['auc'])} & {sgn(dd['diff'], 3)} {ci_txt(dd['ci'])}{stars(dd['p'])} \\\\")
table("panel", [
    "\\resizebox{\\linewidth}{!}{%",
    "\\begin{tabular}{lrrrrlrrl}", "\\toprule",
    " & & & \\multicolumn{3}{c}{Univariate AUC} & \\multicolumn{3}{c}{Out-of-sample logit AUC} \\\\",
    "\\cmidrule(lr){4-6}\\cmidrule(lr){7-9}",
    "Event (next 8 quarters) & Firm-years & Events & Twin & Formula & Best benchmark & Benchmarks & + Twin & $\\Delta$ [95\\% CI] \\\\",
    "\\midrule", *rows, "\\bottomrule", "\\end{tabular}}"])
sb, ab = P["severe_burn"], P["abnormal_burn"]
m("PanTwinAuc", f2(sb["univariate"]["twin"]["auc"]))
m("PanFormulaAuc", f2(sb["univariate"]["formula"]["auc"]))
m("PanFormulaP", pv(sb["univariate"]["formula"]["twin_minus"]["p"]))
m("PanAltmanAuc", f2(sb["univariate"]["altman_z2"]["auc"]))
m("PanIcrAuc", f2(sb["univariate"]["icr"]["auc"]))
m("PanFcfAuc", f2(sb["univariate"]["fcf_margin"]["auc"]))
m("PanOosBench", f2(sb["out_of_sample"]["benchmarks_formula"]["auc"]))
m("PanOosPlus", f2(sb["out_of_sample"]["benchmarks_formula_twin"]["auc"]))
m("PanOosTwinOnly", f2(sb["out_of_sample"]["twin_only"]["auc"]))
m("PanOosDelta", sgn(sb["out_of_sample"]["delta_twin_beyond_formula"]["diff"], 3))
m("PanOosYears", f"{sb['out_of_sample']['test_years'][0]}--{sb['out_of_sample']['test_years'][-1]}")
m("PanLogitZ", f2(sb["clustered_logit"]["twin"]["z"]))
m("PanAbnTwinAuc", f2(ab["univariate"]["twin"]["auc"]))
m("PanAbnEvents", ab["events"])
m("PanNoLoopsAuc", f2(sb["univariate"]["twin_no_loops"]["auc"]))
yrs = sb["auc_by_year"]["twin"]
fcf_best = sum(
    1 for y in yrs if max(sb["auc_by_year"], key=lambda k: sb["auc_by_year"][k][y]) == "fcf_margin"
)
m("PanFcfBestYears", fcf_best)
m("PanYearCount", len(yrs))

# ------------------------------------------------------------------ 5. loops and scenarios
abl, abpb, h12 = C["ablations"], C["ablations_pb_loss"], C.get("ablations_h12", {})
abla = CA["ablations_pb_loss"]
LOOP = {"full": "All loops (full twin)", "no_r1": "without R1 (spread spiral)", "no_r2": "without R2 (market-access cliff)",
        "no_b1": "without B1 (cash conservation)", "no_b2": "without B2 (restructuring)", "no_loops": "without any loop"}
rows = []
for k in LOOP:
    e12 = h12.get(k, {})
    rows.append(f"{LOOP[k]} & {f3(abl[k]['rho'])} & {diff(abl[k]['loss'], 3)} & {f3(abl[k]['rho_pb'])} & "
                f"{diff(abpb.get(k), 3)} & {f3(e12.get('rho_pb'))} & {diff(e12.get('loss_pb'), 3)} & "
                f"{f3(CA['ablations'][k]['rho_pb'])} & {diff(abla.get(k), 3)} \\\\")
table("ablations", [
    "\\begin{tabular}{lrrrrrrrr}", "\\toprule",
    " & \\multicolumn{6}{c}{Raw cash burn} & \\multicolumn{2}{c}{Abnormal burn} \\\\",
    "\\cmidrule(lr){2-7}\\cmidrule(lr){8-9}",
    " & \\multicolumn{4}{c}{8 quarters} & \\multicolumn{2}{c}{12 quarters} & \\multicolumn{2}{c}{8 quarters} \\\\",
    "\\cmidrule(lr){2-5}\\cmidrule(lr){6-7}\\cmidrule(lr){8-9}",
    " & $\\rho$(health) & loss & $\\rho$(breach) & loss & $\\rho$(breach) & loss & $\\rho$(breach) & loss \\\\",
    "\\midrule", *rows, "\\bottomrule", "\\end{tabular}"])
m("AblHealthLoss", f3(abl["no_loops"]["loss"]["diff"]))
m("AblHealthP", pv(abl["no_loops"]["loss"]["p"]))
m("AblPbFull", f2(abl["full"]["rho_pb"]))
m("AblPbNoLoops", f2(abl["no_loops"]["rho_pb"]))
m("AblRtwoLoss", f2(abpb["no_r2"]["diff"]))
m("AblRtwoP", pv(abpb["no_r2"]["p"]))
m("AblAbnRtwoLoss", sgn(abla["no_r2"]["diff"]))
m("AblAbnRtwoP", pv(abla["no_r2"]["p"]))
SCN = {"base": "Baseline", "rates_200": "Rates +200bp", "sales_20": "Sales $-$20\\%", "recession": "Recession",
       "credit_crunch": "Credit crunch", "pandemic": "Demand freeze"}
table("scenarios", [
    "\\begin{tabular}{l" + "r" * len(SCN) + "}", "\\toprule", " & " + " & ".join(SCN.values()) + " \\\\", "\\midrule",
    "Raw burn & " + " & ".join(f2(C["by_scenario"][k]) for k in SCN) + " \\\\",
    "Abnormal burn & " + " & ".join(f2(CA["by_scenario"][k]) for k in SCN) + " \\\\",
    "\\bottomrule", "\\end{tabular}"])
rb_rows = []
for key, label in (("without_added_companies", "Without the five added companies"), ("without_utilities", "Without utilities")):
    r = rb[key]
    rb_rows.append(f"{label} & {r['n']} & {f2(r['rho_twin'])} & {f2(r['rho_baseline'])} & {lower(NAMES[r['best_benchmark']])} & "
                   f"{f2(r['rho_best'])} \\\\")
table("robustness", [
    "\\begin{tabular}{lrrrlr}", "\\toprule", "Sample & $n$ & Twin (stress) & Twin (baseline) & Best benchmark & $\\rho$ \\\\",
    "\\midrule", *rb_rows, "\\bottomrule", "\\end{tabular}"])

# ------------------------------------------------------------------ 6. forecasts
rows = []
for var, label in (("revenue", "Revenue"), ("cash_like", "Cash and short-term investments")):
    v = FC[var]
    cells = []
    for b in ("rw", "ets"):
        x = v[b]
        cells.append(f"{sp(x['skill_scaled'])} & {sp(x['skill_pooled'])} & {pc(x['share_better'])} & {f2(x['dm_t'])}")
    rows.append(f"{label} & {big(v['n'])} & {v['n_firms']} & " + " & ".join(cells) + " \\\\")
table("forecasts", [
    "\\begin{tabular}{lrrrrrrrrrr}", "\\toprule",
    " & & & \\multicolumn{4}{c}{vs.\\ seasonal random walk} & \\multicolumn{4}{c}{vs.\\ ETS} \\\\",
    "\\cmidrule(lr){4-7}\\cmidrule(lr){8-11}",
    " & Pairs & Firms & Skill & Pooled & Better & DM $t$ & Skill & Pooled & Better & DM $t$ \\\\",
    "\\midrule", *rows, "\\bottomrule", "\\end{tabular}"])
fr, fcash = FC["revenue"], FC["cash_like"]
m("FcRevN", big(fr["n"]))
m("FcRevFc", big(round(fr["n"] / 4)))
m("FcRevRw", sp(fr["rw"]["skill_scaled"]))
m("FcRevEts", sp(fr["ets"]["skill_scaled"]))
m("FcRevRwT", f2(fr["rw"]["dm_t"]))
m("FcRevEtsT", f2(fr["ets"]["dm_t"]))
m("FcCashRw", sp(fcash["rw"]["skill_scaled"]))
m("FcCashEts", sp(fcash["ets"]["skill_scaled"]))

# ------------------------------------------------------------------ figures
rows_c = [r for r in C["rows"] if r.get("real_burn") is not None]
h = np.array([r["h_pandemic"] for r in rows_c])
burn = np.array([r["real_burn"] for r in rows_c])
fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.0, 2.7), gridspec_kw={"width_ratios": [1.35, 1]})
a1.scatter(h, np.clip(burn, -80, 40), s=7, color=BLUE, alpha=0.55, lw=0)
off = {"CCL": (10, 6), "RCL": (12, -1), "NCLH": (10, -9), "BA": (8, 2), "WMT": (-6, 9), "AAPL": (4, 6)}
for r in rows_c:
    if r["ticker"] in off:
        a1.annotate(r["ticker"], (r["h_pandemic"], max(r["real_burn"], -80)), fontsize=6.5, color=INK,
                    xytext=off[r["ticker"]], textcoords="offset points", arrowprops={"arrowstyle": "-", "lw": 0.4, "color": MUTED})
a1.axhline(-10, color=ORANGE, lw=0.8, ls="--")
a1.text(98, -9, "severe burn", color=ORANGE, fontsize=6.5, ha="right", va="bottom")
a1.set_xlabel("Twin stress health score, frozen 20 Feb 2020")
a1.set_ylabel("Worst cumulative FCF 2020-21\n(% of trailing revenue, clipped)")
xq = np.arange(5)
a2.bar(xq - 0.19, np.array(q["severe_share"][::-1]) * 100, 0.38, color=BLUE, label="Twin stress score")
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
style = {"twin": (BLUE, 2.0, "Twin"), "formula": ("#1d4f91", 1.0, "Health formula, no simulation"),
         "altman_z2": ("#6e6d66", 1.0, "Altman Z$''$"), "icr": ("#a3a296", 1.0, "Interest coverage"),
         "fcf_margin": (ORANGE, 1.4, "Trailing FCF margin")}
for k, (col, lw, lab) in style.items():
    if k in by:
        ax.plot(years, [by[k][str(y)] for y in years], color=col, lw=lw, marker="o", ms=2.5, label=lab)
ax.axhline(0.5, color=MUTED, lw=0.6, ls=":")
ax.set_ylabel("AUC, severe cash burn\nin the next 8 quarters")
ax.set_xlabel("Cutoff (15 February of)")
ax.legend(ncol=5, fontsize=6.8, loc="lower center", bbox_to_anchor=(0.5, 1.0))
fig.tight_layout()
fig.savefig(FIG / "panel_auc.pdf")
plt.close(fig)

fig, ax = plt.subplots(figsize=(7.0, 1.9))
bk_h = np.array([r["h_pandemic"] for r in BK["firms"]])
bins = np.linspace(0, 100, 26)
ax.hist(h, bins=bins, color="#c9c8bd", label=f"S\\&P 500 non-financials (n={len(h)})", density=True)
ax.hist(bk_h, bins=bins, color=ORANGE, alpha=0.85, label=f"Chapter 11 filers, 2020 (n={len(bk_h)})", density=True)
ax.set_xlabel("Twin stress health score, frozen 20 Feb 2020")
ax.set_yticks([])
ax.legend(fontsize=7)
fig.tight_layout()
fig.savefig(FIG / "bankrupt.pdf")
plt.close(fig)

fig, ax = plt.subplots(figsize=(7.0, 2.3))
ys = sorted(sp_["by_year"], key=int)
ax.bar([int(y) for y in ys], [sp_["by_year"][y]["rho_incremental_cfo"] for y in ys], color=BLUE, width=0.6)
lo, hi = pa["cfo"]["rho_incremental_ci"]
ax.axhspan(lo, hi, color=BLUE, alpha=0.12, lw=0)
ax.axhline(0, color=MUTED, lw=0.6)
ax.set_xticks([int(y) for y in ys])
ax.set_ylabel("Incremental $\\rho$: where the\nmargin rule fails")
ax.set_xlabel("Cutoff (15 February of); realized revenue of the next eight quarters fed into the twin")
fig.tight_layout()
fig.savefig(FIG / "structural.pdf")
plt.close(fig)

(PAPER / "research_numbers.tex").write_text(
    "% generated by engine/scripts/research_assets.py from research.json\n"
    + "\n".join(f"\\newcommand{{\\{k}}}{{{v}}}" for k, v in sorted(macros.items())) + "\n",
    encoding="utf-8",
)
print(f"{len(macros)} macros, {len(list(TAB.glob('*.tex')))} tables -> {PAPER}")
