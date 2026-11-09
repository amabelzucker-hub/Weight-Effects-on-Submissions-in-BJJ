"""Run the full analysis and write the results folder."""
from pathlib import Path

import numpy as np
import pandas as pd

from . import config as cfg
from .cleaning import load_and_clean
from .estimation import CSDiD, boot_summary, twfe
from .plots import plot_events
from .sample import build_panel


def write_summary(path, d, fy, sample, ycols):
    st = fy.groupby("Fighter")["status"].first().value_counts()
    pi = sample.attrs.get("placebo_info", {})
    base = sample[(sample.cohort == 0) | (sample.Year < sample.cohort)]
    with open(path, "w") as f:
        f.write(f"Weight-class matches with sub/decision result, {cfg.YEAR_MIN}-{cfg.YEAR_MAX}: {len(d)}\n")
        f.write(f"Fighter-years with >= {cfg.MIN_MATCHES_PER_YEAR} matches: {len(fy)}\n\n")
        f.write("Fighter trajectories:\n" + st.to_string() + "\n\n")
        f.write(f"Settings: first moves included = {cfg.INCLUDE_FIRST_MOVES}, controls = {cfg.CONTROL_GROUP}, "
                f"placebo years within {cfg.CLEAN_KG}kg, placebo base = {cfg.PLACEBO_BASE}, "
                f"match-count weighting = {cfg.MATCH_COUNT_WEIGHTING}, min movers per event point = {cfg.MIN_POINT_N}\n")
        f.write(f"Placebo data: {pi.get('eligible_pre_move_years')} of {pi.get('pre_move_years')} pre-move fighter-years "
                f"have >= {cfg.MIN_MATCHES_PER_YEAR} matches within {cfg.CLEAN_KG}kg of typical weight "
                f"({pi.get('share_of_pre_move_matches_kept'):.0%} of pre-move matches kept); movers with 2+ eligible years "
                f"(needed for a placebo test): {pi.get('movers_with_2plus_eligible_years')}\n\n")
        for dr in ["up", "down"]:
            coh = sample[sample.direction == dr].groupby("Fighter")["cohort"].first().value_counts().sort_index()
            f.write(f"Cohorts, moved {dr} (year of move):\n" + coh.to_string() + "\n\n")
        f.write(f"Analysis sample: {sample.Fighter.nunique()} fighters, {len(sample)} fighter-years\n")
        f.write("\nBaseline (pre-move / never-treated) mean of each outcome:\n")
        f.write(base[ycols].mean().round(4).to_string() + "\n")
        f.write("\nPre-move typical weight (kg) by group:\n")
        f.write(base.groupby("direction")["wkg"].describe().round(1).to_string() + "\n")


def main(path, outdir="results", plots=True):
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    d = load_and_clean(path)
    fy, sample, ycols = build_panel(d)
    write_summary(out / "sample_summary.txt", d, fy, sample, ycols)
    sample.to_csv(out / "analysis_panel.csv", index=False)

    rows, events, cells, contrasts = [], [], [], []
    for y in ycols:
        fits = {}
        for dr in ["up", "down"]:
            m = CSDiD(sample, y, direction=dr).fit()
            b, se = twfe(sample, y, dr)
            baseline = sample.loc[sample.direction.isin([dr, "never"])
                                  & ((sample.cohort == 0) | (sample.Year < sample.cohort)), y].mean()
            rows.append(m.result | {"twfe": b, "twfe_se": se, "baseline": baseline})
            fits[dr] = m
            events.append(m.event.assign(outcome=y, direction=dr))
            cells.append(m.gt.assign(outcome=y, direction=dr))
        # up = +b + c, down = -b + c  ->  direction effect b, common shift c (same bootstrap draws)
        u, dn = fits["up"].boot_overall, fits["down"].boot_overall
        row = {"outcome": y}
        for name, x in [("diff_up_minus_down", u - dn), ("direction_effect", (u - dn) / 2),
                        ("common_shift", (u + dn) / 2)]:
            v, se_, lo, hi = boot_summary(x)
            row |= {name: v, f"{name}_se": se_, f"{name}_lo": lo, f"{name}_hi": hi}
        contrasts.append(row)
        print(f"{y:38s} up={fits['up'].result['att']:+.3f}  down={fits['down'].result['att']:+.3f}  "
              f"direction={row['direction_effect']:+.3f} [{row['direction_effect_lo']:+.3f},{row['direction_effect_hi']:+.3f}]  "
              f"common={row['common_shift']:+.3f} [{row['common_shift_lo']:+.3f},{row['common_shift_hi']:+.3f}]")
    res, con = pd.DataFrame(rows), pd.DataFrame(contrasts)
    res.to_csv(out / "att_overall.csv", index=False)
    con.to_csv(out / "up_vs_down.csv", index=False)
    pd.concat(events).to_csv(out / "event_study.csv", index=False)
    pd.concat(cells).to_csv(out / "att_gt.csv", index=False)
    if plots:
        plot_events(pd.concat(events), out)
    return res, con
