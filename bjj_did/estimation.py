"""Step 3: Callaway & Sant'Anna (2021) staggered difference-in-differences,
plus a naive two-way fixed-effects regression for contrast."""
import numpy as np
import pandas as pd

from . import config as cfg


def boot_summary(x):
    """x[0] = point estimate, x[1:] = bootstrap draws -> (estimate, se, 2.5%, 97.5%)."""
    b = x[1:][~np.isnan(x[1:])]
    if len(b) < 2:
        return x[0], np.nan, np.nan, np.nan
    return x[0], b.std(ddof=1), np.percentile(b, 2.5), np.percentile(b, 97.5)


class CSDiD:
    """Group-time ATTs on an unbalanced competitor-year panel.

    For each move-year cohort g and calendar year t, ATT(g, t) is the movers'
    change in the outcome minus the comparison group's change over the same years:
      after the move (t >= g)  compare t with g-1, using full-year outcomes
      placebo (t < g)          use the filtered placebo outcomes; compare t with the
                               mover's last eligible pre-move year (PLACEBO_BASE =
                               "last_clean") or with t-1 ("previous")
    A competitor enters a comparison only if observed in both of its years.

    Comparison group (CONTROL_GROUP): never-movers ("never"), or never-movers plus
    competitors of either direction who have not moved yet in both years ("notyet").

    With MATCH_COUNT_WEIGHTING, each competitor's change is weighted by its precision,
    1 / (1/n_t + 1/n_base) with n = matches that year. Cohort-year results are then
    averaged by number of movers into an overall effect and an event study.
    Event-study points resting on fewer than MIN_POINT_N movers are dropped and
    don't count toward the overall or placebo averages.

    Inference: nonparametric bootstrap resampling whole competitors. The full panel
    (both directions) is always used to index competitors, so the same seed gives
    identical draws for movers up and movers down, and their difference has a
    valid standard error.
    """

    def __init__(self, panel, ycol, direction="up", control=None, min_units=1):
        control = control or cfg.CONTROL_GROUP
        wide = panel.pivot(index="Fighter", columns="Year", values=ycol)
        years = np.array(wide.columns)
        Y = wide.values

        def piv(col):
            return panel.pivot(index="Fighter", columns="Year", values=col).reindex(index=wide.index, columns=years).values

        N, Yc, Nc = piv("n"), piv(ycol + "__clean"), piv("n_clean")
        first = panel.groupby("Fighter")[["cohort", "direction", "clean_until"]].first().reindex(wide.index)
        coh_all = first["cohort"].values.copy()          # every mover's move year (either direction)
        clean_until = first["clean_until"].values        # last placebo-eligible pre-move year (0 = none)
        coh = coh_all.copy()
        coh[(first["direction"] != direction).values & (coh > 0)] = -1   # other direction: never treated here
        yi = {y: i for i, y in enumerate(years)}
        self.direction, self.ycol, self.n = direction, ycol, len(coh)
        self.cells = []        # (g, t, base, treated idx, control idx, dy, precision weight)

        def add(g, t, base, tr, placebo=False):
            if base not in yi or t not in yi or t == base:
                return
            Yu, Nu = (Yc, Nc) if placebo else (Y, N)
            dy = Yu[:, yi[t]] - Yu[:, yi[base]]
            ok = ~np.isnan(dy)
            if control == "never":
                ctrl = coh_all == 0
            else:
                ctrl = (coh_all == 0) | ((coh_all > max(t, base)) & (coh_all != g))
            it, ic = np.where(tr & ok)[0], np.where(ctrl & ok)[0]
            if len(it) >= min_units and len(ic) >= 2:
                if cfg.MATCH_COUNT_WEIGHTING:
                    with np.errstate(invalid="ignore", divide="ignore"):
                        pw = np.nan_to_num(1.0 / (1.0 / Nu[:, yi[t]] + 1.0 / Nu[:, yi[base]]))
                else:
                    pw = np.ones(len(dy))
                self.cells.append((g, t, base, it, ic, np.nan_to_num(dy), pw))

        for g in sorted(c for c in np.unique(coh) if c > 0):
            tr_g = coh == g
            for t in years:
                if t >= g:
                    add(g, t, g - 1, tr_g)
            if cfg.PLACEBO_BASE == "last_clean":
                for c in sorted(set(clean_until[tr_g]) - {0}):
                    for t in years:
                        if t < c:
                            add(g, t, c, tr_g & (clean_until == c), placebo=True)
            else:
                for t in years:
                    if t < g:
                        add(g, t, t - 1, tr_g & (clean_until >= t), placebo=True)

    def _att(self, W):
        """W: (draws x competitors) bootstrap counts -> ATT and mover counts (draws x cells)."""
        att, nt = [], []
        for g, t, base, it, ic, dy, pw in self.cells:
            wt, wc = W[:, it], W[:, ic]
            vt, vc = wt * pw[it], wc * pw[ic]
            st, sc = vt.sum(1), vc.sum(1)
            with np.errstate(invalid="ignore", divide="ignore"):
                a = (vt @ dy[it]) / st - (vc @ dy[ic]) / sc
            a[(st == 0) | (sc == 0)] = np.nan
            att.append(a)
            nt.append(np.where(np.isnan(a), 0, wt.sum(1)))
        return np.array(att).T, np.array(nt).T

    @staticmethod
    def _wavg(a, w, mask):
        a = np.where(mask, np.nan_to_num(a), 0.0)
        w = np.where(mask, w, 0.0)
        with np.errstate(invalid="ignore", divide="ignore"):
            return (a * w).sum(1) / w.sum(1)

    def fit(self, n_boot=None, seed=None, emin=-4, emax=3, min_point_n=None):
        n_boot = cfg.N_BOOT if n_boot is None else n_boot
        seed = cfg.SEED if seed is None else seed
        min_point_n = cfg.MIN_POINT_N if min_point_n is None else min_point_n
        rng = np.random.default_rng(seed)
        W = np.vstack([np.ones(self.n),
                       rng.multinomial(self.n, np.ones(self.n) / self.n, size=n_boot)]).astype(float)
        att, nt = self._att(W)
        e = np.array([t - g for g, t, *_ in self.cells])
        n_e = {k: int(nt[0][e == k].sum()) for k in np.unique(e)}   # movers behind each point
        valid = np.array([n_e[k] >= min_point_n for k in e])
        self.dropped_points = sorted(int(k) for k, v in n_e.items() if v < min_point_n)
        overall = self._wavg(att, nt, (e >= 0) & valid)
        pre = self._wavg(att, nt, (e < 0) & valid)
        o, se, lo, hi = boot_summary(overall)
        p, pse, plo, phi = boot_summary(pre)
        self.boot_overall, self.boot_pre = overall, pre
        post_cells = [c[3] for c, v, k in zip(self.cells, valid, e) if v and k >= 0]
        pre_cells = [c[3] for c, v, k in zip(self.cells, valid, e) if v and k < 0]
        self.result = {"outcome": self.ycol, "direction": self.direction, "att": o, "se": se, "ci_lo": lo, "ci_hi": hi,
                       "pre_avg": p, "pre_se": pse, "pre_lo": plo, "pre_hi": phi,
                       "n_treated_post": int(np.unique(np.concatenate(post_cells)).size) if post_cells else 0,
                       "n_treated_pre": int(np.unique(np.concatenate(pre_cells)).size) if pre_cells else 0,
                       "dropped_points": " ".join(map(str, self.dropped_points))}
        rows, self.boot_es = [], {}
        for k in range(emin, emax + 1):
            m = (e == k) & valid
            if m.any():
                self.boot_es[k] = self._wavg(att, nt, m)
                v, s_, l, h = boot_summary(self.boot_es[k])
                rows.append((k, v, s_, l, h, n_e[k]))
        self.event = pd.DataFrame(rows, columns=["e", "att", "se", "lo", "hi", "n"])
        self.gt = pd.DataFrame({"g": [c[0] for c in self.cells], "t": [c[1] for c in self.cells],
                                "base": [c[2] for c in self.cells],
                                "att": att[0], "n_treated": nt[0], "used": valid})
        return self


def twfe(panel, ycol, direction="up"):
    """Naive two-way fixed-effects regression, for contrast only:
        y = beta * post + competitor effect + year effect
    Biased under staggered timing with effects that vary by cohort or over time,
    because already-moved competitors act as controls for later movers.
    Unweighted, never-movers as controls. Returns (beta, competitor-clustered se)."""
    p = panel[panel["direction"].isin([direction, "never"])].copy()
    p["post"] = ((p["cohort"] > 0) & (p["Year"] >= p["cohort"])).astype(float)
    X, Y = p["post"].values.copy(), p[ycol].values.copy()
    for _ in range(200):                     # remove competitor and year means by alternating projections
        for key in ["Fighter", "Year"]:
            X = X - pd.Series(X).groupby(p[key].values).transform("mean").values
            Y = Y - pd.Series(Y).groupby(p[key].values).transform("mean").values
    beta = (X @ Y) / (X @ X)
    sc = pd.Series(X * (Y - beta * X)).groupby(p["Fighter"].values).sum().values
    return beta, np.sqrt((sc ** 2).sum()) / (X @ X)
