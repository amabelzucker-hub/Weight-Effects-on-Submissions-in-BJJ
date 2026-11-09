"""The estimator recovers a known effect from simulated data.

Each competitor's outcome = their own level + a year shock + EFFECT after moving,
with no noise, so every after-move comparison must equal EFFECT exactly and every
placebo comparison must equal zero, under every setting combination.
"""
import itertools

import numpy as np
import pandas as pd
import pytest

from bjj_did import CSDiD, config as cfg, twfe

EFFECT = 0.10
Y = "Submission win (finished opponent)"


def simulated_panel(seed=1):
    rng = np.random.default_rng(seed)
    years = np.arange(2012, 2021)
    shock = dict(zip(years, rng.normal(0, 0.05, len(years))))
    groups = [("never", 0)] * 30 + [("up", 2015)] * 8 + [("up", 2017)] * 8 + [("down", 2016)] * 8
    rows = []
    for i, (direction, cohort) in enumerate(groups):
        level = rng.uniform(0.2, 0.4)
        sign = -1 if direction == "down" else 1
        for t in years:
            if rng.random() < 0.15:                      # unbalanced: some years missing
                continue
            y = level + shock[t] + (sign * EFFECT if cohort and t >= cohort else 0.0)
            n = int(rng.integers(3, 25))
            rows.append(dict(Fighter=f"f{i}", Year=t, cohort=cohort, direction=direction,
                             n=n, n_clean=n, **{Y: y, Y + "__clean": y}))
    p = pd.DataFrame(rows)
    last_pre = p[(p.cohort > 0) & (p.Year < p.cohort)].groupby("Fighter").Year.max()
    p["clean_until"] = p.Fighter.map(last_pre).fillna(0).astype(int)
    return p


@pytest.mark.parametrize("weighted, control, base",
                         list(itertools.product([True, False], ["never", "notyet"], ["last_clean", "previous"])))
def test_recovers_known_effect(weighted, control, base):
    cfg.MATCH_COUNT_WEIGHTING, cfg.CONTROL_GROUP, cfg.PLACEBO_BASE = weighted, control, base
    p = simulated_panel()
    for direction, truth in [("up", EFFECT), ("down", -EFFECT)]:
        m = CSDiD(p, Y, direction).fit(n_boot=20, min_point_n=1)
        post, pre = m.gt[m.gt.t >= m.gt.g], m.gt[m.gt.t < m.gt.g]
        assert len(post) and len(pre)
        np.testing.assert_allclose(post.att, truth, atol=1e-12)
        np.testing.assert_allclose(pre.att, 0.0, atol=1e-12)
        assert m.result["att"] == pytest.approx(truth, abs=1e-12)


def test_naive_twfe_is_exact_when_effect_is_constant():
    # with one constant effect and no noise, even the naive regression is right;
    # its bias only appears when effects differ by cohort or over time
    beta, _ = twfe(simulated_panel(), Y, "up")
    assert beta == pytest.approx(EFFECT, abs=1e-6)


def test_up_and_down_share_bootstrap_draws():
    p = simulated_panel()
    up, down = CSDiD(p, Y, "up").fit(n_boot=50), CSDiD(p, Y, "down").fit(n_boot=50)
    # same competitors drawn in each resample -> direction effect has no spurious noise here
    direction = (up.boot_overall - down.boot_overall) / 2
    np.testing.assert_allclose(direction, EFFECT, atol=1e-12)
