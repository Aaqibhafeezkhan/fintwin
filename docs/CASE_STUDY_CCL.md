# Case study: Carnival, February 2020

*What a financial digital twin could and could not see before the cruise industry shut down.*

## The information set

The twin was calibrated with `asof="2020-02-20"`. Its last visible quarter was **fiscal Q4 2019 (ending 30 Nov 2019)**, and every later fact and restatement is invisible to it. At that point Carnival was a healthy, investment-grade operator:

* revenue of about $20.8B a year with stable seasonality
* about $9.7B of total debt and a thin cash buffer of about $0.5B
* about $4.7B of customer deposits, which is cash collected ahead of sailings

## What the twin said

| Scenario (Feb 2020 view) | Health score | P(liquidity breach, 2y) | P(sub-investment grade) |
|---|---|---|---|
| Baseline | **71** | 0% | 0% |
| Demand freeze (−70% revenue, markets shut 2 quarters) | **12** | 100% | ~100% |

The baseline was benign, as it should be: nothing in the filings predicted a pandemic. The value lies in the conditional answer. Under a demand freeze, Carnival's twin collapsed harder than almost any other company in the 30-name universe. Three structural features combine:

1. **Operating leverage.** Most ship-operating costs are fixed, so EBITDA turns deeply negative when revenue stops.
2. **Customer deposits.** A revenue stop also triggers refunds of advance bookings, a cash outflow on top of the operating loss.
3. **The R1/R2 loops.** Collapsing coverage pushes the synthetic rating to CCC, which narrows market access to 30% of needs, at punitive spreads.

## What actually happened

| | Q4 2019 (last seen) | Peak 2020–21 |
|---|---|---|
| Quarterly revenue | $4.8B | under $0.1B for four straight quarters |
| Total debt | $9.7B | $28.5B (Nov 2021) |
| Cash & ST investments | $0.5B | $11.5B (hoarded from emergency raises) |

Carnival survived by raising roughly $19B of net new debt, much of it secured at double-digit coupons, plus equity. The twin's mechanics describe this path. The twin itself does not reach it, because its base settings don't allow emergency equity and only partial market access below 0.8× coverage.

## Structural test

When the twin is fed the *realized* revenue path, its cumulative free cash flow over Q1 2020–Q4 2021 is **−$12.8B, against an actual −$17.6B**. That is the right direction and shape (quarterly correlation 0.66), with burn under-estimated by about 28%. The gap comes from fixed ship costs and deposit refunds running above the calibrated cost structure. An industry-specific "fleet lay-up cost" parameter would be the natural next refinement.

## Takeaways

* The twin **cannot forecast** the shock, and the unconditional fan missed it entirely. That is the correct behaviour, and the backtest reports it.
* The twin **does rank fragility**. Before COVID, its stress health score put the three cruise lines and Boeing near the bottom of 88 companies (Spearman ρ = 0.51 with realized cash burn, p < 10⁻⁶).
* In the Stress Lab, flipping on *Emergency equity raise* and running *Demand freeze* reproduces the strategy Carnival actually used to survive.
