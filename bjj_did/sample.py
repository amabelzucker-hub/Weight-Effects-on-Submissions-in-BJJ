"""Step 2: outcomes, weight-class trajectories and the competitor-year panel."""
import numpy as np
import pandas as pd

from . import config as cfg

FAMILIES = ["Choke", "Arm lock", "Leg lock"]
SPECIFIC_SUBS = ["Rear naked choke", "Armbar", "Triangle", "Guillotine",
                 "Heel hook", "Kneebar", "Toe hold", "Straight ankle lock"]


def build_outcomes(d):
    """One 0/1 column per outcome, one row per match (from the competitor's side).

    Any submission = submission win + submission loss. Every family and specific
    submission is split by who got the finish: "Win ..." = the competitor
    submitted the opponent with it, "Loss ..." = the competitor was submitted.
    """
    sub = (d["outcome"] == "sub").astype(float)
    win, loss = (d["W/L"] == "W"), (d["W/L"] == "L")
    out = {
        "Any submission": sub,
        "Submission win (finished opponent)": sub * win,
        "Submission loss (got finished)": sub * loss,
    }
    for side, mask in [("Win", win), ("Loss", loss)]:
        for fam in FAMILIES:
            out[f"{side} family: {fam}"] = ((d["family"] == fam) & mask).astype(float)
        for spec in SPECIFIC_SUBS:
            out[f"{side} specific: {spec}"] = ((d["specific"] == spec) & mask).astype(float)
    return pd.DataFrame(out, index=d.index)


def classify_trajectory(g):
    """Label one competitor from their yearly typical weights (sorted by year).

    Returns (status, move_year, last_year_kept):
      never        typical weight never moved more than WITHIN_KG
      up1/down1    exactly one move of >= STEP_KG that persists to the end
      up_first/    moved more than once, but the FIRST move is clean: a stable
      down_first   spell, then a jump of >= STEP_KG that holds into the next
                   observed year. Years after the class changes again are
                   dropped, so only the first move is studied.
      other        no clean first move (unstable from the start, or a one-year trip)
      single       only one usable year
    """
    x, yrs = g["wkg"].values, g["Year"].values
    if len(x) < 2:
        return "single", np.nan, np.nan
    if x.max() - x.min() <= cfg.WITHIN_KG:
        return "never", np.nan, np.nan
    for k in range(1, len(x)):
        before, after = x[:k], x[k:]
        if np.ptp(before) <= cfg.WITHIN_KG and np.ptp(after) <= cfg.WITHIN_KG:
            if after.min() - before.max() >= cfg.STEP_KG:
                return "up1", yrs[k], np.nan
            if before.min() - after.max() >= cfg.STEP_KG:
                return "down1", yrs[k], np.nan
    for k in range(1, len(x)):                   # first clean move of a multi-mover
        before = x[:k]
        if np.ptp(before) > cfg.WITHIN_KG:
            break                                # unstable before any clean move
        up = x[k] - before.max() >= cfg.STEP_KG
        down = before.min() - x[k] >= cfg.STEP_KG
        if not (up or down):
            continue
        j = k + 1                                # follow the new class until it changes again
        while j < len(x) and np.ptp(x[k:j + 1]) <= cfg.WITHIN_KG:
            j += 1
        if j - k < 2:
            break                                # one-year trip into another class
        return ("up_first" if up else "down_first"), yrs[k], yrs[j - 1]
    return "other", np.nan, np.nan


def build_panel(d):
    """Match data -> competitor-year panel.

    Returns (fy, sample, outcome_columns):
      fy      every competitor-year with >= MIN_MATCHES_PER_YEAR matches, with trajectory status
      sample  the analysis panel: movers (up/down) and never-movers, with
                cohort      move year (0 = never moved)
                direction   'up', 'down' or 'never'
                <outcome>__clean, n_clean
                            placebo versions of each outcome, built only from matches
                            within CLEAN_KG of typical weight (NaN if fewer than
                            MIN_MATCHES_PER_YEAR such matches)
                clean_until last placebo-eligible pre-move year (0 = none)
    """
    Y = build_outcomes(d)
    m = pd.concat([d[["Fighter", "Year", "wkg"]], Y], axis=1)
    agg = {"wkg": "median", **{c: "mean" for c in Y.columns}}
    fy = m.groupby(["Fighter", "Year"]).agg(agg)
    fy["n"] = m.groupby(["Fighter", "Year"]).size()
    fy = fy[fy["n"] >= cfg.MIN_MATCHES_PER_YEAR].reset_index()

    traj = fy.sort_values("Year").groupby("Fighter")[["wkg", "Year"]].apply(classify_trajectory)
    t = pd.DataFrame(traj.tolist(), index=traj.index, columns=["status", "cohort", "last_year"])
    fy = fy.merge(t, left_on="Fighter", right_index=True)
    keep = ["up1", "down1", "never"] + (["up_first", "down_first"] if cfg.INCLUDE_FIRST_MOVES else [])
    sample = fy[fy["status"].isin(keep)].copy()
    sample = sample[sample["last_year"].isna() | (sample["Year"] <= sample["last_year"])]
    sample["direction"] = sample["status"].map({"up1": "up", "up_first": "up", "down1": "down",
                                                "down_first": "down", "never": "never"})
    sample["cohort"] = sample["cohort"].fillna(0).astype(int)

    # Placebo outcomes. Before a move, competitors often already fight some matches at the
    # new weight, which would leak post-move behaviour into the placebo checks. So placebo
    # checks use outcomes built only from matches within CLEAN_KG of typical weight
    # (movers: median of pre-move years; never-movers: median of all years). The same
    # filter applies to comparison competitors. After-move estimates use full years.
    pre = sample[(sample["cohort"] > 0) & (sample["Year"] < sample["cohort"])]
    typical = pd.concat([pre.groupby("Fighter")["wkg"].median(),
                         sample[sample["cohort"] == 0].groupby("Fighter")["wkg"].median()])
    dm = m[m["Fighter"].isin(typical.index)]
    if cfg.CLEAN_KG is not None:
        dm = dm[(dm["wkg"] - dm["Fighter"].map(typical)).abs() <= cfg.CLEAN_KG]
    cl = dm.groupby(["Fighter", "Year"])[list(Y.columns)].mean().add_suffix("__clean")
    cl["n_clean"] = dm.groupby(["Fighter", "Year"]).size()
    cl = cl[cl["n_clean"] >= cfg.MIN_MATCHES_PER_YEAR]
    sample = sample.merge(cl, left_on=["Fighter", "Year"], right_index=True, how="left")
    elig = sample[(sample["cohort"] > 0) & (sample["Year"] < sample["cohort"]) & sample["n_clean"].notna()]
    sample = sample.merge(elig.groupby("Fighter")["Year"].max().rename("clean_until"),
                          left_on="Fighter", right_index=True, how="left")
    movers = sample.loc[sample["cohort"] > 0].groupby("Fighter")[["direction", "clean_until"]].first()
    two = elig.groupby("Fighter").size().ge(2)
    sample["clean_until"] = sample["clean_until"].fillna(0).astype(int)
    sample.attrs["placebo_info"] = {
        "movers": int(len(movers)), "pre_move_years": int(len(pre)), "eligible_pre_move_years": int(len(elig)),
        "movers_with_2plus_eligible_years": two[two].index.map(movers["direction"]).value_counts().to_dict(),
        "share_of_pre_move_matches_kept": round(float(elig["n_clean"].sum() / pre["n"].sum()), 3)}
    return fy, sample, list(Y.columns)
