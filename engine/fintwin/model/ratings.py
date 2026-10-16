"""Synthetic credit rating from interest coverage (Damodaran, large non-financial firms, Jan 2026).

Source: https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/ratings.html
Rank 0 = D ... 14 = AAA. Spreads are over the risk-free rate, decimal p.a.
"""

import numpy as np

# Lower ICR bound of each bucket (bucket i covers [LOWER[i], LOWER[i+1]) ).
ICR_LOWER = np.array([-np.inf, 0.2, 0.65, 0.8, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5, 3.0, 4.25, 5.5, 6.5, 8.5])
RATINGS = ["D", "C", "CC", "CCC", "B-", "B", "B+", "BB", "BB+", "BBB", "A-", "A", "A+", "AA", "AAA"]
SPREADS = np.array(
    [0.19, 0.16, 0.1261, 0.0885, 0.0509, 0.0321, 0.0275, 0.0184, 0.0138, 0.0111, 0.0089, 0.0078, 0.0070, 0.0055, 0.0040]
)
INVESTMENT_GRADE_MIN_RANK = 9  # BBB


def rating_rank(icr: np.ndarray) -> np.ndarray:
    return np.searchsorted(ICR_LOWER, icr, side="right") - 1


def rating_spread(icr: np.ndarray) -> np.ndarray:
    return SPREADS[rating_rank(icr)]
