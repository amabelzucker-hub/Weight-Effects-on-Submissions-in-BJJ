"""Weight labels and match results are parsed as intended."""
import math

import pytest

from bjj_did import classify_method, weight_kg


@pytest.mark.parametrize("label, kg", [
    ("76KG", 76), ("76 KG", 76), ("57KG", 57),
    ("O94KG", 100), ("94KG+", 100),          # "over X" sits one class step above X
    ("120KG", 100), ("O100KG", 100),         # everything >= 100kg is one heavyweight group
])
def test_weight_labels(label, kg):
    assert weight_kg(label) == kg


@pytest.mark.parametrize("label", ["ABS", "SPF", "35KG", None])
def test_non_weight_labels_are_dropped(label):
    assert math.isnan(weight_kg(label))


@pytest.mark.parametrize("method, expected", [
    # decisions
    ("Pts: 2x0", ("dec", None, None)), ("Points", ("dec", None, None)),
    ("Referee Decision", ("dec", None, None)), ("Adv", ("dec", None, None)),
    # excluded results
    ("DQ", (None, None, None)), ("EBI/OT", (None, None, None)), ("Injury", (None, None, None)),
    # tricky submissions: rule order matters
    ("Omoplata choke", ("sub", "Choke", None)),
    ("Choke from omoplata", ("sub", "Choke", None)),
    ("Arm triangle", ("sub", "Choke", None)),          # a choke, but not a triangle
    ("Triangle armbar", ("sub", "Arm lock", None)),    # an armbar finished from triangle
    ("Triangle", ("sub", "Choke", "Triangle")),
    # spelling variants and synonyms
    ("Inside heel hook", ("sub", "Leg lock", "Heel hook")),
    ("Botinha", ("sub", "Leg lock", "Straight ankle lock")),
    ("RNC", ("sub", "Choke", "Rear naked choke")),
    ("Choke from back", ("sub", "Choke", "Rear naked choke")),
    ("Armbar", ("sub", "Arm lock", "Armbar")),
    ("Kimura", ("sub", "Arm lock", None)),
    ("Darce", ("sub", "Choke", None)),
    ("Submission", ("sub", "Other / unspecified", None)),
])
def test_match_results(method, expected):
    assert classify_method(method) == expected
