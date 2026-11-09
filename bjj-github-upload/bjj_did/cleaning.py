"""Step 1: read the match file and clean weight labels and match results."""
import re

import numpy as np
import pandas as pd

from . import config as cfg


def weight_kg(label):
    """Weight label -> kg.

    '76KG' -> 76; 'O94KG' (over 94) -> 100, one class step above; anything at or
    above HEAVY_CAP -> HEAVY_CAP. Open-class (ABS), stage codes typed into the
    weight column and other junk -> NaN.
    """
    if not isinstance(label, str):
        return np.nan
    s = label.upper().replace(" ", "")
    m = re.match(r"^([OU]?)(\d+)(KG|K|KF|G)?(\+)?$", s)
    if not m:
        return np.nan
    x = float(m.group(2))
    if x < 40 or x > 130:
        return np.nan
    if m.group(1) == "O" or m.group(4):    # open-ended "over X" class sits one step above X
        x += 6
    return min(x, cfg.HEAVY_CAP)


DECISION_RE = re.compile(r"^(pts\b|points|referee decision|adv|advantages|pen)", re.I)
EXCLUDE_RE = re.compile(r"^(---|dq|injury|inj\b|ebi|tko|exhaustion|pressure ?/ ?injury)", re.I)

# (pattern, specific submission or None, family). Checked in order, first match wins,
# so the special cases come first (e.g. an omoplata choke is a choke, an arm triangle
# is a choke but not a "triangle").
SUB_RULES = [
    (r"heel ho", "Heel hook", "Leg lock"),
    (r"toe ho", "Toe hold", "Leg lock"),
    (r"knee ?bar|dogbar", "Kneebar", "Leg lock"),
    (r"straig\w* an\w+ lock|foot ?lock|botinha|ankle lock|estima", "Straight ankle lock", "Leg lock"),
    (r"calf|leg ?lock|aoki|terra|mikey|suloev|shin lock|toe hook|z lock|junny|banana", None, "Leg lock"),
    (r"choke f\w*\.? ?/? ?omoplata|omoplata ?[-/ ]?choke|omoplata/rnc", None, "Choke"),
    (r"arm[- ]?triangle|no[- ]arm triang", None, "Choke"),
    (r"triangle ?[-/ ]?(arm|kimura|shl|shoulder|wrist|w/)|kimura ?[-/f]+ ?triangle", None, "Arm lock"),
    (r"choke from (the )?back|^rnc|arm in rnc|mata leao|possible rnc", "Rear naked choke", "Choke"),
    (r"guillotin|guilotine|marcelotine", "Guillotine", "Choke"),
    (r"triang|sankaku|cryangle", "Triangle", "Choke"),
    (r"arm ?bar|arnbar|^armlock|straight armlock", "Armbar", "Arm lock"),
    (r"kimura|americana|omoplata|wris\w*lock|shoulder lock|bicep|tarikoplata|baratoplata|"
     r"monoplata|manoplata|marceloplata|mir (arm)?lock|violin|armlock|policeman|carney", None, "Arm lock"),
    (r"choke|ezek|ezequiel|darce|anaconda|kata ?ga|katagame|necktie|bow and arrow|"
     r"bread|brabo|clock|loop|baseball|gogoplata|crucifix|cachecol|smother|neck crank|muffler|"
     r"amassa", None, "Choke"),
]
SUB_RULES = [(re.compile(p, re.I), s, f) for p, s, f in SUB_RULES]


def classify_method(method):
    """Match result -> (outcome, family, specific).

    outcome is 'sub', 'dec' (points, advantages, referee decision, penalties) or
    None (excluded: DQ, injury, EBI overtime, ...).
    """
    if not isinstance(method, str) or EXCLUDE_RE.match(method.strip()):
        return None, None, None
    method = method.strip()
    if DECISION_RE.match(method):
        return "dec", None, None
    for rx, spec, fam in SUB_RULES:
        if rx.search(method):
            return "sub", fam, spec
    # taps without a recognised technique ("Submission", "Verbal tap", "Knee on belly", ...)
    return "sub", "Other / unspecified", None


def load_and_clean(path):
    """Read the BJJ Heroes match file and keep weight-class matches with a
    submission or decision result, YEAR_MIN-YEAR_MAX. Draws are dropped."""
    d = pd.read_csv(path)
    d = d[d["W/L"].isin(["W", "L"])].copy()
    d["wkg"] = d["Weight"].map(weight_kg)
    cls = d["Method"].map(classify_method)
    d["outcome"] = [c[0] for c in cls]
    d["family"] = [c[1] for c in cls]
    d["specific"] = [c[2] for c in cls]
    d = d[d["outcome"].notna() & d["wkg"].notna()]
    return d[d["Year"].between(cfg.YEAR_MIN, cfg.YEAR_MAX)]
