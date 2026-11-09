"""Shared test setup.

Tests that need the real match data look for data.csv in the project folder
(or the path in the BJJ_DATA environment variable) and are skipped if it's missing.
"""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bjj_did import build_panel, config as cfg, load_and_clean  # noqa: E402

DATA = Path(os.environ.get("BJJ_DATA", ROOT / "data.csv"))


@pytest.fixture(autouse=True)
def default_settings():
    """Every test starts and ends with the default settings."""
    cfg.reset()
    yield
    cfg.reset()


@pytest.fixture(scope="session")
def real_panel():
    if not DATA.exists():
        pytest.skip(f"match data not found at {DATA}")
    cfg.reset()
    d = load_and_clean(DATA)
    fy, sample, ycols = build_panel(d)
    return d, fy, sample, ycols
