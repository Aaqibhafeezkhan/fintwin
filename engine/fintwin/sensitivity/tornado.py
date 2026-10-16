"""One-at-a-time sensitivity of the health score and breach probability to each stress knob."""

from __future__ import annotations

from ..stochastic.mc import run, summarize
from ..stochastic.shocks import draw_shocks

FACTORS = [
    ("sales_depth", 0.3, "Revenue -30%"),
    ("rate_bp", 300, "Rates +300bp"),
    ("spread_bp", 400, "Spreads +400bp"),
    ("cost_pp", 5.0, "Costs +5pp"),
    ("refi_freeze", 4, "Debt markets shut 4q"),
    ("dio_days", 45, "Inventory +45 days"),
]


def tornado(p: dict, n_paths: int = 2000, seed: int = 13) -> list[dict]:
    eps = draw_shocks(p, n_paths, p["horizon"], seed)
    base = summarize(run(p, {}, eps=eps))
    rows = []
    for knob, value, label in FACTORS:
        s = summarize(run(p, {knob: value}, eps=eps))
        rows.append(
            {
                "knob": knob,
                "value": value,
                "label": label,
                "d_health": s["health_score"] - base["health_score"],
                "d_p_breach": s["p_breach"] - base["p_breach"],
            }
        )
    return sorted(rows, key=lambda r: r["d_health"])
