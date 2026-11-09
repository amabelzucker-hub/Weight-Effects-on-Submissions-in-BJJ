"""Individual comparisons recomputed by hand from the real panel must match the estimator.

Each check rebuilds one movers-vs-comparison calculation directly with pandas:
change in the outcome between two years, weighted by match precision
1 / (1/n_t + 1/n_base), movers minus comparison group (never-movers plus
competitors who haven't moved yet in either year).
"""
import numpy as np
import pytest

from bjj_did import CSDiD

CASES = [   # (outcome, direction, after the move?)
    ("Submission win (finished opponent)", "up", True),
    ("Submission win (finished opponent)", "down", True),
    ("Submission win (finished opponent)", "down", False),
    ("Loss family: Leg lock", "down", True),
    ("Loss family: Leg lock", "up", False),
    ("Any submission", "up", True),
]


def by_hand(sample, y, direction, g, t, base, placebo):
    col, ncol = (y + "__clean", "n_clean") if placebo else (y, "n")
    w = sample.pivot(index="Fighter", columns="Year", values=col)
    n = sample.pivot(index="Fighter", columns="Year", values=ncol)
    info = sample.groupby("Fighter")[["cohort", "direction", "clean_until"]].first()
    dy = (w[t] - w[base]).dropna()
    pw = 1 / (1 / n.loc[dy.index, t] + 1 / n.loc[dy.index, base])
    f = info.loc[dy.index]
    movers = (f.cohort == g) & (f.direction == direction)
    if placebo:
        movers &= f.clean_until == base
    controls = (f.cohort == 0) | ((f.cohort > max(t, base)) & (f.cohort != g))
    return np.average(dy[movers], weights=pw[movers]) - np.average(dy[controls], weights=pw[controls])


@pytest.mark.parametrize("y, direction, post", CASES)
def test_cells_match_hand_calculation(real_panel, y, direction, post):
    _, _, sample, _ = real_panel
    gt = CSDiD(sample, y, direction).fit(n_boot=2).gt
    cells = gt[(gt.t >= gt.g) if post else (gt.t < gt.g)]
    for _, r in cells.sample(5, random_state=0).iterrows():
        expected = by_hand(sample, y, direction, int(r.g), int(r.t), int(r.base), placebo=not post)
        assert r.att == pytest.approx(expected, abs=1e-12)


def test_win_plus_loss_equals_any_submission(real_panel):
    d, _, sample, _ = real_panel
    total = sample["Submission win (finished opponent)"] + sample["Submission loss (got finished)"]
    np.testing.assert_allclose(total, sample["Any submission"], atol=1e-12)
