"""
Build the data and Python estimates that validate_did.R compares against the R `did` package.

The project's main settings (match weights, 2kg placebo filter, last-clean-year placebo base)
are custom, so the comparison uses the plain Callaway & Sant'Anna setup that `did` implements:
never-movers as controls, unweighted, year-before (varying) placebo base, all matches.

Two datasets:
  balanced  2017-2020, competitors observed every year: should match `did` exactly.
  full      2010-2023 unbalanced panel: `did` handles missing years with a different
            (repeated cross-section) estimator, so expect close but not identical numbers.

Usage (from the project folder):  python3 r_validation/make_validation_data.py data.csv
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from bjj_did import CSDiD, build_panel, config as cfg, load_and_clean

DATA = sys.argv[1] if len(sys.argv) > 1 else str(HERE.parent / "data.csv")
OUTCOMES = {"sub_win": "Submission win (finished opponent)",
            "sub_loss": "Submission loss (got finished)",
            "sub_any": "Any submission"}
WINDOW = (2017, 2020)

# plain C&S configuration
cfg.CLEAN_KG = None
cfg.MATCH_COUNT_WEIGHTING = False
cfg.PLACEBO_BASE = "previous"
cfg.CONTROL_GROUP = "never"
cfg.MIN_POINT_N = 0

d = load_and_clean(DATA)
fy, panel, _ = build_panel(d)
ids = {f: i + 1 for i, f in enumerate(sorted(panel["Fighter"].unique()))}


def balanced(p):
    y0, y1 = WINDOW
    w = p[p["Year"].between(y0, y1)].copy()
    full = w.groupby("Fighter")["Year"].nunique().loc[lambda s: s == y1 - y0 + 1].index
    w = w[w["Fighter"].isin(full)]
    # keep never-movers and movers whose move falls inside the window (after its first year)
    keep = (w["cohort"] == 0) | ((w["cohort"] > y0) & (w["cohort"] <= y1))
    return w[keep].copy()


datasets = {"full": panel.copy(), "balanced": balanced(panel)}
rows = []
for name, p in datasets.items():
    out = p[["Fighter", "Year", "cohort", "direction"] + list(OUTCOMES.values())].copy()
    out.insert(0, "id", out["Fighter"].map(ids))
    out = out.rename(columns={v: k for k, v in OUTCOMES.items()}).drop(columns="Fighter")
    out.to_csv(HERE / f"panel_{name}.csv", index=False)
    for short, y in OUTCOMES.items():
        for dr in ["up", "down"]:
            sub = p[p["direction"].isin([dr, "never"])]          # same sample `did` gets
            m = CSDiD(sub, y, dr).fit(n_boot=999)
            base = dict(dataset=name, direction=dr, outcome=short)
            for _, r in m.gt.iterrows():
                rows.append(base | dict(type="att_gt", g=int(r.g), t=int(r.t), e=int(r.t - r.g), estimate=r.att, se=np.nan))
            R = m.result
            rows.append(base | dict(type="simple", g=np.nan, t=np.nan, e=np.nan, estimate=R["att"], se=R["se"]))
            for _, r in m.event.iterrows():
                rows.append(base | dict(type="dynamic", g=np.nan, t=np.nan, e=int(r.e), estimate=r.att, se=r.se))
pd.DataFrame(rows).to_csv(HERE / "python_estimates.csv", index=False)
for name, p in datasets.items():
    f = p.groupby("Fighter")[["cohort", "direction"]].first()
    print(name, len(p), "rows;", f["direction"].value_counts().to_dict())
