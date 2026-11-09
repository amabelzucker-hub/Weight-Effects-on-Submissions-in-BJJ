"""
Compare the strict original sample with the expanded versions.

    python3 compare_specs.py data.csv [results_folder]

  Strict (original)   competitors who changed class exactly once; never-movers as controls
  + first moves       also the first clean move of competitors who moved more than once
  + not-yet controls  competitors who move later also serve as controls before their move
  Both (new main)     both changes (the default settings)

Writes spec_comparison.csv and spec_event_study.csv.
"""
import sys

import numpy as np
import pandas as pd

from bjj_did import CSDiD, build_panel, config as cfg, load_and_clean

SPECS = [("Strict (original)", False, "never"), ("+ first moves", True, "never"),
         ("+ not-yet controls", False, "notyet"), ("Both (new main)", True, "notyet")]
OUTCOMES = ["Any submission", "Submission win (finished opponent)", "Submission loss (got finished)",
            "Win family: Leg lock", "Loss family: Leg lock", "Win family: Choke", "Loss family: Choke"]


def run(data, out):
    rows, ev = [], []
    for name, first_moves, control in SPECS:
        cfg.reset()
        cfg.INCLUDE_FIRST_MOVES, cfg.CONTROL_GROUP = first_moves, control
        fy, s, _ = build_panel(load_and_clean(data))
        for y in OUTCOMES:
            f = {dr: CSDiD(s, y, dr).fit() for dr in ["up", "down"]}
            u, dn = f["up"].boot_overall, f["down"].boot_overall
            r = dict(spec=name, outcome=y, n_up=s[s.direction == "up"].Fighter.nunique(),
                     n_down=s[s.direction == "down"].Fighter.nunique())
            for dr in ["up", "down"]:
                R = f[dr].result
                r |= {dr: R["att"], f"{dr}_se": R["se"], f"{dr}_pre": R["pre_avg"],
                      f"{dr}_pre_lo": R["pre_lo"], f"{dr}_pre_hi": R["pre_hi"]}
                ev.append(f[dr].event.assign(spec=name, outcome=y, direction=dr))
            for k, x in [("direction", (u - dn) / 2), ("common", (u + dn) / 2)]:
                bb = x[1:][~np.isnan(x[1:])]
                r |= {k: x[0], f"{k}_lo": np.percentile(bb, 2.5), f"{k}_hi": np.percentile(bb, 97.5)}
            rows.append(r)
    cfg.reset()
    R, E = pd.DataFrame(rows), pd.concat(ev)
    R.to_csv(f"{out}/spec_comparison.csv", index=False)
    E.to_csv(f"{out}/spec_event_study.csv", index=False)
    return R


if __name__ == "__main__":
    data = sys.argv[1] if len(sys.argv) > 1 else "data.csv"
    out = sys.argv[2] if len(sys.argv) > 2 else "results"
    pd.set_option("display.width", 250)
    print(run(data, out).round(3).to_string())
