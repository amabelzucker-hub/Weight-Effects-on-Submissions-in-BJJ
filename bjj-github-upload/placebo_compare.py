"""
Compare placebo-check methods across all outcomes.

    python3 placebo_compare.py data.csv [results_folder]

All four use the 2kg match filter; they differ in what each pre-move year is
compared with (the year before, or the last clean pre-move year) and whether
changes are weighted by match counts. Writes placebo_comparison.csv and
placebo_event_study.csv, and prints how many placebo points fail.
"""
import sys

import numpy as np
import pandas as pd

from bjj_did import CSDiD, build_panel, config as cfg, load_and_clean

SPECS = [("Year before, unweighted", "previous", False), ("Year before, weighted", "previous", True),
         ("Last clean year, unweighted", "last_clean", False),
         ("Last clean year, weighted (new main)", "last_clean", True)]


def run(data, out):
    rows, evs = [], []
    for name, placebo_base, weighted in SPECS:
        cfg.reset()
        cfg.PLACEBO_BASE, cfg.MATCH_COUNT_WEIGHTING = placebo_base, weighted
        fy, s, ycols = build_panel(load_and_clean(data))
        for y in ycols:
            f = {dr: CSDiD(s, y, dr).fit() for dr in ["up", "down"]}
            u, dn = f["up"].boot_overall, f["down"].boot_overall
            r = dict(spec=name, outcome=y)
            for dr in ["up", "down"]:
                R = f[dr].result
                r |= {dr: R["att"], f"{dr}_lo": R["ci_lo"], f"{dr}_hi": R["ci_hi"], f"{dr}_pre": R["pre_avg"],
                      f"{dr}_pre_lo": R["pre_lo"], f"{dr}_pre_hi": R["pre_hi"], f"{dr}_n_pre": R["n_treated_pre"]}
                evs.append(f[dr].event.assign(spec=name, outcome=y, direction=dr))
            for k, x in [("direction", (u - dn) / 2), ("common", (u + dn) / 2)]:
                bb = x[1:][~np.isnan(x[1:])]
                r |= {k: x[0], f"{k}_lo": np.percentile(bb, 2.5), f"{k}_hi": np.percentile(bb, 97.5)}
            rows.append(r)
    cfg.reset()
    R, E = pd.DataFrame(rows), pd.concat(evs)
    R.to_csv(f"{out}/placebo_comparison.csv", index=False)
    E.to_csv(f"{out}/placebo_event_study.csv", index=False)
    return R, E


if __name__ == "__main__":
    data = sys.argv[1] if len(sys.argv) > 1 else "data.csv"
    out = sys.argv[2] if len(sys.argv) > 2 else "results"
    R, E = run(data, out)
    P = E[E.e < 0].assign(fail=lambda x: (x.lo > 0) | (x.hi < 0))
    summ = P.groupby("spec", sort=False).agg(points=("fail", "size"), failing=("fail", "sum"))
    summ["expected_by_chance"] = (summ.points * .05).round(1)
    avg = R.assign(up_pre_fail=lambda x: (x.up_pre_lo > 0) | (x.up_pre_hi < 0),
                   down_pre_fail=lambda x: (x.down_pre_lo > 0) | (x.down_pre_hi < 0)
                   ).groupby("spec", sort=False)[["up_pre_fail", "down_pre_fail"]].sum()
    print(summ.join(avg).to_string())
