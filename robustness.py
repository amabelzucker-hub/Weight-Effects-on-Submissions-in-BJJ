"""
Rerun key outcomes under different cleaning thresholds.

    python3 robustness.py data.csv [results_folder]

Varies the minimum matches per year and the move rule (step / wobble in kg),
keeping every other setting at its default. Writes robustness.csv.
"""
import sys

import pandas as pd

from bjj_did import CSDiD, build_panel, config as cfg, load_and_clean

THRESHOLDS = [(3, 5, 4), (2, 5, 4), (5, 5, 4), (3, 4, 3), (3, 6, 4)]   # (min matches, step kg, wobble kg)
OUTCOMES = ["Any submission", "Submission win (finished opponent)", "Submission loss (got finished)",
            "Win family: Leg lock", "Loss family: Leg lock", "Win family: Choke", "Loss family: Choke"]


def run(data, out):
    rows = []
    for mm, step, wk in THRESHOLDS:
        cfg.reset()
        cfg.MIN_MATCHES_PER_YEAR, cfg.STEP_KG, cfg.WITHIN_KG = mm, step, wk
        fy, s, _ = build_panel(load_and_clean(data))
        for y in OUTCOMES:
            u, dn = CSDiD(s, y, "up").fit(), CSDiD(s, y, "down").fit()
            dirn = (u.boot_overall - dn.boot_overall) / 2
            c = (u.boot_overall + dn.boot_overall) / 2
            rows.append(dict(min_matches=mm, step=step, within=wk,
                             n_up=s[s.direction == "up"].Fighter.nunique(),
                             n_down=s[s.direction == "down"].Fighter.nunique(),
                             controls=s[s.direction == "never"].Fighter.nunique(), outcome=y,
                             up=u.result["att"], down=dn.result["att"],
                             direction=dirn[0], direction_se=dirn[1:].std(), common=c[0], common_se=c[1:].std()))
    cfg.reset()
    R = pd.DataFrame(rows)
    R.to_csv(f"{out}/robustness.csv", index=False)
    return R


if __name__ == "__main__":
    data = sys.argv[1] if len(sys.argv) > 1 else "data.csv"
    out = sys.argv[2] if len(sys.argv) > 2 else "results"
    print(run(data, out).round(3).to_string())
