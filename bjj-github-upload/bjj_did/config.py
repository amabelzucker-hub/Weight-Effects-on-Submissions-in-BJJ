"""Analysis settings.

Every choice in the analysis is a named setting here, so a choice can be changed
without touching the logic. The comparison scripts change these values, run the
analysis, then call reset() to restore the defaults below.
"""

DEFAULTS = {
    # --- sample ---
    "YEAR_MIN": 2010,
    "YEAR_MAX": 2023,
    "MIN_MATCHES_PER_YEAR": 3,    # competitor-years with fewer weight-class matches are dropped
    "STEP_KG": 5,                 # a move must shift typical weight by >= this (one class step)
    "WITHIN_KG": 4,               # wobble still counted as the same class (federation labels differ by 1-3kg)
    "HEAVY_CAP": 100,             # all labels >= 100kg (incl. 110/120/O100) form one heavyweight group
    "INCLUDE_FIRST_MOVES": True,  # also use the first clean move of competitors who moved more than once
    # --- estimation ---
    "CONTROL_GROUP": "notyet",    # "never" = never-movers only; "notyet" = never-movers + movers before their move
    "MATCH_COUNT_WEIGHTING": True, # weight each competitor's year-to-year change by how many matches it rests on
    # --- placebo checks ---
    "CLEAN_KG": 2,                # placebo checks only count matches within this many kg of typical weight (None = all)
    "PLACEBO_BASE": "last_clean", # compare each pre-move year with: "last_clean" year, or "previous" year
    "MIN_POINT_N": 4,             # event-study points (and the placebo average) need at least this many movers
    # --- inference ---
    "N_BOOT": 999,                # bootstrap draws (resampling whole competitors)
    "SEED": 20261105,
}

globals().update(DEFAULTS)


def reset():
    """Restore every setting to its default."""
    globals().update(DEFAULTS)


def current():
    """The settings in force right now, as a dict."""
    return {k: globals()[k] for k in DEFAULTS}
