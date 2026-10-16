"""Generate the paper's figures and a numbers.tex of LaTeX macros straight from the exported results.

Every figure and every number quoted in docs/paper/fintwin.tex comes from this script, so the paper cannot
drift from the data.
"""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "web" / "public" / "data"
OUT = ROOT / "docs" / "paper"
FIG = OUT / "figures"
FIG.mkdir(parents=True, exist_ok=True)

BLUE, ORANGE, INK, MUTED, GRID = "#2a78d6", "#eb6834", "#0b0b0b", "#898781", "#e1e0d9"
plt.rcParams.update({
    "font.family": "sans-serif", "font.size": 8.5, "axes.edgecolor": "#c3c2b7", "axes.linewidth": 0.8,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
    "axes.spines.top": False, "axes.spines.right": False, "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.labelcolor": "#52514e", "figure.dpi": 200, "savefig.bbox": "tight",
})

cal = json.loads((DATA / "calibration.json").read_text(encoding="utf-8"))
bt = json.loads((DATA / "backtest.json").read_text(encoding="utf-8"))
idx = json.loads((DATA / "index.json").read_text(encoding="utf-8"))
macros: dict[str, str] = {}


def m(name: str, value) -> None:
    macros[name] = str(value)


def usd(x):
    """Signed billions with a typographic minus, e.g. $-$\$12.1B."""
    return ("$-$" if x < 0 else "") + "\\$" + f"{abs(x) / 1e9:.1f}B"


def pct(x, d=0):
    return f"{x * 100:.{d}f}\\%"


# ---- headline numbers ----
xs = cal["cross_section"]
m("NCompanies", cal["n_companies"])
m("NForecasts", f"{cal['n_forecasts']:,}".replace(",", "{,}"))
m("NOrigins", len(cal["origins"]))
m("XsN", xs["n"])
m("XsRho", f"{xs['spearman']:.2f}")
m("XsP", "<0.001" if xs["p_value"] < 0.001 else f"{xs['p_value']:.3f}")
m("XsCiLo", f"{xs['ci95'][0]:.2f}")
m("XsCiHi", f"{xs['ci95'][1]:.2f}")
rows_q = sorted((r for r in xs["rows"] if r.get("realized_min_cum_fcf_pct_rev") is not None),
                key=lambda r: r["health_stress"])
k = len(rows_q) * 2 // 5
fragile, robust = rows_q[:k], rows_q[-k:]
m("XsSevereFragile", f"{100 * np.mean([r['realized_min_cum_fcf_pct_rev'] < -10 for r in fragile]):.0f}\\%")
m("XsSevereRobust", f"{100 * np.mean([r['realized_min_cum_fcf_pct_rev'] < -10 for r in robust]):.0f}\\%")
for var, tag in (("revenue", "Rev"), ("cash_like", "Cash")):
    v = cal["vars"][var]
    m(f"{tag}RawNinety", pct(v["raw"]["coverage90"]))
    m(f"{tag}ConfNinety", pct(v["conformal"]["coverage90"]))
    m(f"{tag}RawFifty", pct(v["raw"]["coverage50"]))
    m(f"{tag}ConfFifty", pct(v["conformal"]["coverage50"]))
    m(f"{tag}Skill", pct(v["crps_skill_vs_naive"]))
    m(f"{tag}Beat", pct(v["share_cases_beating_naive"]))
    m(f"{tag}RegimeGain", f"{v['regime_ablation']['improvement_pct']:.1f}\\%")
    m(f"{tag}N", f"{v['n']:,}".replace(",", "{,}"))
m("NDashboard", len(idx["companies"]))
for key, f in bt["forecast"].items():
    s = f.get("structural") or {}
    if s:
        tk, ck = key.split(":")
        tag = tk.replace(".", "") + ("Covid" if ck == "pre_covid" else "Hikes")
        m(f"Struct{tag}Err", f"{s['final_error_pct']:.0f}\\%")
        m(f"Struct{tag}Model", usd(s['model_cum_fcf_bands'][2][-1]))
        m(f"Struct{tag}Actual", usd(s['actual_cum_fcf'][-1]))
        m(f"Struct{tag}Corr", f"{s['corr']:.2f}" if s.get("corr") is not None else "--")
ccl = bt["forecast"]["CCL:pre_covid"]["pre_shock"]
m("CclBaseHealth", f"{ccl['base']['health_score']:.0f}")
m("CclStressHealth", f"{ccl['stress']['health_score']:.0f}")

(OUT / "numbers.tex").write_text("".join(f"\\newcommand{{\\{k}}}{{{v}}}\n" for k, v in macros.items()), encoding="utf-8")

# ---- Figure 1: cross-section ----
rows = [r for r in xs["rows"] if r.get("realized_min_cum_fcf_pct_rev") is not None]
fig, ax = plt.subplots(figsize=(5.2, 3.2))
x = np.array([r["health_stress"] for r in rows])
y = np.array([r["realized_min_cum_fcf_pct_rev"] for r in rows])
ax.scatter(x, y, s=16, color=BLUE, edgecolor="white", linewidth=0.6, zorder=3)
label = {"CCL", "RCL", "NCLH", "BA", "AAL", "UAL", "MSFT", "GOOGL", "WMT", "EXPE", "LVS", "WYNN", "ABNB", "UBER"}
for r in rows:
    if r["ticker"] in label:
        ax.annotate(r["ticker"], (r["health_stress"], r["realized_min_cum_fcf_pct_rev"]), xytext=(4, 3),
                    textcoords="offset points", fontsize=6.5, color="#52514e")
ax.axhline(0, color="#c3c2b7", lw=0.8)
ax.set_xlabel("Twin health score under 'demand freeze', calibrated Feb 2020")
ax.set_ylabel("Realized worst cum. FCF 2020-21, % revenue")
fig.savefig(FIG / "cross_section.pdf")
plt.close(fig)

# ---- Figure 2: PIT histograms + coverage by year ----
fig, axes = plt.subplots(1, 3, figsize=(7.0, 2.3))
for ax, (var, title) in zip(axes[:2], (("revenue", "Revenue"), ("cash_like", "Cash"))):
    h = np.array(cal["vars"][var]["pit_hist"])
    ax.bar(np.arange(10) * 0.1 + 0.05, h, width=0.085, color=BLUE)
    ax.axhline(0.1, color=INK, lw=0.8, ls="--")
    ax.set_title(f"PIT, {title.lower()}", fontsize=8.5, color=INK)
    ax.set_xlim(0, 1)
    ax.set_xlabel("PIT value")
axes[0].set_ylabel("Share of forecasts")
by = cal["vars"]["revenue"]["by_year"]
years = sorted(by)
axes[2].bar(range(len(years)), [by[y]["cov90"] for y in years], color=[ORANGE if y in ("2019", "2020") else BLUE for y in years])
axes[2].axhline(0.9, color=INK, lw=0.8, ls="--")
axes[2].set_xticks(range(len(years)))
axes[2].set_xticklabels([f"'{y[2:]}" for y in years], rotation=90)
axes[2].set_title("Raw 90% coverage by cutoff", fontsize=8.5, color=INK)
axes[2].set_ylim(0, 1)
fig.tight_layout()
fig.savefig(FIG / "calibration.pdf")
plt.close(fig)

# ---- Figure 3: Carnival pre-COVID forecast vs reality, and structural test ----
f = bt["forecast"]["CCL:pre_covid"]
fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.5))
s = f["series"]["revenue"]
nh, nf = len(s["history"]["values"]), len(s["realized"]["values"])
xh, xf = np.arange(nh), np.arange(nh - 1, nh + nf)
ax = axes[0]
ax.plot(xh, np.array(s["history"]["values"]) / 1e9, color=INK, lw=1.4)
for bands, col, lab in ((s["base_bands"], BLUE, "Baseline"), (s["stress_bands"], ORANGE, "Demand freeze")):
    b = np.array(bands)[:, :nf] / 1e9
    anchor = s["history"]["values"][-1] / 1e9
    ax.fill_between(xf, np.r_[anchor, b[0]], np.r_[anchor, b[4]], color=col, alpha=0.15, lw=0)
    ax.plot(xf, np.r_[anchor, b[2]], color=col, lw=1.4, label=lab)
ax.plot(np.arange(nh, nh + nf), np.array([v if v is not None else np.nan for v in s["realized"]["values"]]) / 1e9,
        "o-", color=INK, ms=3, lw=1, label="Reported")
ax.set_title("Carnival revenue ($B), twin calibrated Feb 2020", fontsize=8.5, color=INK)
ax.set_xticks([])
ax.legend(frameon=False, fontsize=6.5)
st = f["structural"]
ax = axes[1]
b = np.array(st["model_cum_fcf_bands"]) / 1e9
xx = np.arange(len(st["dates"]))
ax.fill_between(xx, b[0], b[4], color=BLUE, alpha=0.15, lw=0)
ax.plot(xx, b[2], color=BLUE, lw=1.4, label="Twin (fed realized revenue)")
ax.plot(xx, np.array(st["actual_cum_fcf"]) / 1e9, "o-", color=INK, ms=3, lw=1, label="Actual")
ax.set_title("Cumulative free cash flow ($B), 2020-21", fontsize=8.5, color=INK)
ax.set_xticks(xx[::2])
ax.set_xticklabels([d[:7] for d in st["dates"]][::2], rotation=45, fontsize=6.5)
ax.legend(frameon=False, fontsize=6.5)
fig.tight_layout()
fig.savefig(FIG / "carnival.pdf")
plt.close(fig)

# ---- Figure 4: Sobol for three contrasting companies ----
picks = [t for t in ("CCL", "BA", "INTC") if (DATA / "companies" / f"{t}.json").exists()]
fig, axes = plt.subplots(1, len(picks), figsize=(7.0, 2.1), sharey=True)
for ax, t in zip(np.atleast_1d(axes), picks):
    sob = json.loads((DATA / "companies" / f"{t}.json").read_text(encoding="utf-8")).get("sobol")
    if not sob:
        continue
    rows_s = sorted(sob["rows"], key=lambda r: r["knob"])
    labels = [r["label"] for r in rows_s]
    yy = np.arange(len(rows_s))
    ax.barh(yy, [r["ST"] for r in rows_s], color=BLUE, alpha=0.3, height=0.55)
    ax.barh(yy, [r["S1"] for r in rows_s], color=BLUE, height=0.55)
    ax.set_yticks(yy)
    ax.set_yticklabels(labels)
    ax.set_xlim(0, 1)
    ax.set_title(t, fontsize=8.5, color=INK)
fig.tight_layout()
fig.savefig(FIG / "sobol.pdf")
plt.close(fig)
print(f"{len(macros)} macros, figures in {FIG}")
