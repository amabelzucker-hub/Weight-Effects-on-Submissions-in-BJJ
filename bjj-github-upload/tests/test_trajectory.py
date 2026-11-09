"""Competitors are labelled correctly from their yearly typical weight
(defaults: a move is a shift of >= 5kg; wobble of <= 4kg is the same class)."""
import math

import pandas as pd
import pytest

from bjj_did import classify_trajectory


def traj(*kg, start=2014):
    return classify_trajectory(pd.DataFrame({"Year": range(start, start + len(kg)), "wkg": kg}))


def test_never_moved_with_federation_wobble():
    # AJP -85 vs IBJJF -88.3 style wobble is not a move
    assert traj(85, 88, 85, 86)[0] == "never"


def test_single_move_up():
    status, move_year, _ = traj(76, 76, 82, 82)
    assert (status, move_year) == ("up1", 2016)


def test_single_move_down():
    status, move_year, _ = traj(88, 88, 82, 82, 82)
    assert (status, move_year) == ("down1", 2016)


def test_first_move_of_multi_mover_is_kept_until_next_change():
    status, move_year, last_year = traj(70, 70, 76, 76, 82)
    assert (status, move_year, last_year) == ("up_first", 2016, 2017)


def test_one_year_trip_is_not_a_move():
    # a single season one class up, then back down
    assert traj(70, 70, 76, 70, 70)[0] == "other"


def test_one_year_only():
    status, move_year, _ = traj(76)
    assert status == "single" and math.isnan(move_year)
