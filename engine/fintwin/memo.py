"""AI analyst: grounded credit memos written by Claude from the twin's simulation output.

Design choices that make the memos trustworthy rather than decorative:
* Claude sees only a compact fact sheet built from the exported simulation (no web, no memory of the company);
  the prompt forbids numbers that are not in it.
* The answer is constrained to a JSON schema (structured outputs), so the dashboard renders fields, not prose blobs.
* A deterministic number checker extracts every figure in the memo and matches it against the fact sheet.
  Memos with unmatched numbers are regenerated once with the offending figures named; anything still unmatched
  is flagged in the UI instead of hidden.
* Memos are generated at build time and committed as JSON, so the public site needs no API key.

    uv run --extra ai python -m fintwin.memo CCL AAPL      # needs ANTHROPIC_API_KEY (or an `ant auth login` profile)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from .model.ratings import RATINGS

# A key in the project's git-ignored .env wins over a stale shell variable.
load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=True)

DATA = Path(__file__).resolve().parents[2] / "web" / "public" / "data"
MODEL = "claude-opus-5-5"

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["verdict", "headline", "summary", "key_risks", "resilience", "scenario_notes", "watch_list"],
    "properties": {
        "verdict": {"type": "string", "enum": ["Strong", "Adequate", "Watch", "Weak", "Distressed"]},
        "headline": {"type": "string", "description": "One sentence, at most 25 words."},
        "summary": {"type": "string", "description": "3-4 sentences for a credit committee."},
        "key_risks": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["risk", "evidence"],
            "properties": {"risk": {"type": "string"}, "evidence": {"type": "string"}}}},
        "resilience": {"type": "array", "items": {"type": "string"}},
        "scenario_notes": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["scenario", "note"],
            "properties": {"scenario": {"type": "string"}, "note": {"type": "string"}}}},
        "watch_list": {"type": "array", "items": {"type": "string"},
                       "description": "Observable indicators in future filings that would change the view."},
    },
}

SYSTEM = """You are a senior credit analyst writing for a credit committee.
You are given a fact sheet produced by a calibrated Monte Carlo digital twin of a company's finances.
Rules:
- Use ONLY numbers that appear in the fact sheet. Round as the sheet does. Never invent figures, dates, events,
  products, or management actions that are not in the sheet. If something is unknown, do not mention it.
- Explain mechanisms (operating leverage, maturities, market access, coverage, customer deposits) rather than
  repeating numbers; every risk needs evidence from the sheet.
- Be calibrated: the baseline is a forecast under normal conditions; scenarios are conditional what-ifs, not predictions.
- Plain, precise English. No hype, no investment advice."""


def _money(x: float) -> str:
    a = abs(x)
    s = "-" if x < 0 else ""
    return f"{s}${a / 1e9:.1f}B" if a >= 1e9 else f"{s}${a / 1e6:.0f}M"


def fact_sheet(c: dict, meta: dict) -> dict:
    p, base = c["params"], c["presets"]["base"]
    hist = c["history"]["series"]
    last_rating = next((r for r in reversed(hist["rating"]) if r is not None), None)
    rev_ttm = sum(x for x in hist["revenue"][-4:] if x is not None)
    sheet = {
        "company": c["name"], "ticker": c["ticker"], "sector": c["sector"], "last_reported_quarter": p["last_quarter"],
        "horizon_quarters": p["horizon"], "simulated_paths": 5000,
        "reported": {
            "revenue_last_4_quarters": _money(rev_ttm),
            "cash_and_short_term_investments": _money(p["cash0"]),
            "total_debt": _money(p["debt0"]),
            "synthetic_rating_today": RATINGS[int(last_rating)] if last_rating is not None else "n/a",
            "debt_maturing_next_4_quarters": _money(sum(p["maturities_q"][:4])),
            "committed_credit_facility": _money(p["revolver_cap"]),
            "customer_deposits_days_of_revenue": round(p["ddays"]),
        },
        "calibrated_structure": {
            "fixed_costs_per_quarter": _money(p["F"]),
            "variable_cost_share_of_revenue_pct": round(p["v"] * 100),
            "trend_growth_pct_per_year": round(((1 + p["mu"]) ** 4 - 1) * 100, 1),
            "demand_volatility_pct_per_quarter": round(p["sigma_g"] * 100, 1),
            "average_cost_of_debt_pct": round(p["coupon"] * 100, 1),
            "revenue_sensitivity_to_gdp": round(p.get("beta_gdp", 1.5), 1),
        },
        "scenarios": {},
        "reverse_stress": {},
        "sensitivity_tornado_health_change": {t["label"]: round(t["d_health"], 1) for t in c["tornado"]},
    }
    for key, v in c["presets"].items():
        label = meta["presets"][key]["label"]
        sheet["scenarios"][label] = {
            "description": meta["presets"][key]["desc"],
            "health_score_0_100": round(v["health_score"]),
            "health_score_unluckiest_10pct": round(v["health_p10"]),
            "prob_liquidity_breach_pct": round(v["p_breach"] * 100, 1),
            "prob_interest_coverage_below_1_5x_pct": round(v["p_icr_below_1_5"] * 100),
            "prob_sub_investment_grade_at_horizon_pct": round(v["p_downgrade_below_ig"] * 100),
        }
    for key, r in c["reverse_stress"].items():
        unit = {"pct": "% revenue drop", "bp": "bp rate rise", "pp": "pp cost increase"}[r["unit"]]
        conv = (lambda v: round(v * 100)) if r["unit"] == "pct" else (lambda v: round(v))
        sheet["reverse_stress"][r["label"]] = {
            "shock_for_50pct_breach": f"{conv(r['p50'])}{unit}" if r["p50"] is not None else "not reached (company can fund itself)",
            "shock_for_10pct_breach": f"{conv(r['p10'])}{unit}" if r["p10"] is not None else "not reached",
        }
    if c.get("sobol"):
        sheet["global_sensitivity_total_order_pct"] = {r["label"]: round(r["ST"] * 100) for r in c["sobol"]["rows"]}
    return sheet


NUM = re.compile(r"-?\$?\d+(?:,\d{3})*(?:\.\d+)?")


def _numbers(text: str) -> list[float]:
    out = []
    for m in NUM.findall(text):
        try:
            out.append(float(m.replace("$", "").replace(",", "")))
        except ValueError:
            pass
    return out


def unverified_numbers(memo: dict, sheet: dict) -> list[float]:
    """Figures in the memo that cannot be matched to the fact sheet (after rounding)."""
    allowed = set(_numbers(json.dumps(sheet)))
    allowed |= {abs(a) for a in allowed}
    bad = []
    for x in _numbers(json.dumps(memo)):
        if abs(x) <= 12 or 1990 <= x <= 2035:  # quarter counts, ordinal words, years
            continue
        if not any(abs(abs(x) - a) <= max(0.051 * abs(a), 0.6) for a in allowed):
            bad.append(x)
    return bad


def write_memo(client: anthropic.Anthropic, sheet: dict, feedback: str | None = None) -> dict:
    user = ("Fact sheet (JSON):\n" + json.dumps(sheet, indent=1) +
            "\n\nWrite the credit memo. 3-5 key risks, 2-4 resilience factors, a note for each stress scenario"
            " that matters for this company (at least 4), and 3-4 watch-list indicators.")
    if feedback:
        user += "\n\n" + feedback
    resp = client.beta.messages.create(
        model=MODEL,
        max_tokens=8000,
        system=SYSTEM,
        messages=[{"role": "user", "content": user}],
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if resp.stop_reason == "refusal":
        raise RuntimeError(f"refused: {resp.stop_details}")
    if resp.stop_reason == "max_tokens":
        raise RuntimeError("memo truncated at max_tokens")
    text = next(b.text for b in resp.content if b.type == "text")
    return {"memo": json.loads(text), "model": resp.model,
            "usage": {"input": resp.usage.input_tokens, "output": resp.usage.output_tokens}}


def build(tickers: list[str]) -> None:
    client = anthropic.Anthropic()
    index = json.loads((DATA / "index.json").read_text(encoding="utf-8"))
    out_dir = DATA / "memos"
    out_dir.mkdir(exist_ok=True)
    for t in tickers:
        c = json.loads((DATA / "companies" / f"{t}.json").read_text(encoding="utf-8"))
        sheet = fact_sheet(c, index["meta"])
        r = write_memo(client, sheet)
        bad = unverified_numbers(r["memo"], sheet)
        attempts = 1
        if bad:
            r = write_memo(client, sheet, feedback=f"Your previous draft used figures not in the fact sheet: {bad}. "
                                                   "Remove or correct every one of them.")
            bad = unverified_numbers(r["memo"], sheet)
            attempts = 2
        (out_dir / f"{t}.json").write_text(json.dumps({
            "ticker": t, "generated_by": r["model"], "as_of": c["params"]["last_quarter"], "attempts": attempts,
            "unverified_numbers": bad, "fact_sheet": sheet, **r["memo"], "usage": r["usage"]}, indent=1), encoding="utf-8")
        print(f"{t}: {r['memo']['verdict']} | attempts={attempts} unverified={bad} tokens={r['usage']}")


if __name__ == "__main__":
    build([a.upper() for a in sys.argv[1:]])
