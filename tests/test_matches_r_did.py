"""On a balanced panel, the estimator reproduces the R `did` package exactly.

Uses r_validation/panel_balanced.csv and the R results in r_validation/did_estimates.csv
(made by validate_did.R). Plain Callaway & Sant'Anna settings: never-movers as controls,
unweighted, year-before placebo base, all matches.

The panel is built from the match data, which isn't distributed with this repository:
with data.csv in place, run `python3 r_validation/make_validation_data.py data.csv` to
create it. Skipped if the panel or the R results are missing.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from bjj_did import CSDiD, config as cfg

RV = Path(__file__).resolve().parents[1] / "r_validation"
OUTCOMES = {"sub_win": "Submission win (finished opponent)",
            "sub_loss": "Submission loss (got finished)",
            "sub_any": "Any submission"}


@pytest.fixture(scope="module")
def r_results():
    path = RV / "did_estimates.csv"
    if not path.exists():
        pytest.skip("run r_validation/validate_did.R first")
    if not (RV / "panel_balanced.csv").exists():
        pytest.skip("run r_validation/make_validation_data.py data.csv first (needs the match data)")
    return pd.read_csv(path)


def balanced_panel():
    p = pd.read_csv(RV / "panel_balanced.csv").rename(columns={"id": "Fighter"})
    for short, long in OUTCOMES.items():
        p[long] = p[long + "__clean"] = p.pop(short)
    p["n"] = p["n_clean"] = 1
    last_pre = p[(p.cohort > 0) & (p.Year < p.cohort)].groupby("Fighter").Year.max()
    p["clean_until"] = p.Fighter.map(last_pre).fillna(0).astype(int)
    return p


@pytest.mark.parametrize("direction", ["up", "down"])
@pytest.mark.parametrize("short", list(OUTCOMES))
def test_balanced_panel_matches_r(r_results, direction, short):
    cfg.CONTROL_GROUP, cfg.MATCH_COUNT_WEIGHTING, cfg.PLACEBO_BASE, cfg.MIN_POINT_N = "never", False, "previous", 0
    p = balanced_panel()
    p = p[p.direction.isin([direction, "never"])]
    m = CSDiD(p, OUTCOMES[short], direction).fit(n_boot=2)
    r = r_results[(r_results.dataset == "balanced") & (r_results.direction == direction)
                  & (r_results.outcome == short)]

    gt_r = r[r.type == "att_gt"].set_index(["g", "t"]).estimate
    gt_py = m.gt.set_index(["g", "t"]).att
    assert set(gt_py.index) == set(gt_r.index)
    np.testing.assert_allclose(gt_py.sort_index(), gt_r.sort_index(), atol=1e-10)

    simple_r = r[r.type == "simple"].estimate.iloc[0]
    assert m.result["att"] == pytest.approx(simple_r, abs=1e-10)

    dyn_r = r[r.type == "dynamic"].set_index("e").estimate
    dyn_py = m.event.set_index("e").att
    shared = dyn_py.index.intersection(dyn_r.index)
    np.testing.assert_allclose(dyn_py.loc[shared], dyn_r.loc[shared], atol=1e-10)
