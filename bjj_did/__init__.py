"""
Staggered difference-in-differences: does changing weight class change how often
BJJ competitors finish opponents, or get finished themselves?

Data: BJJ Heroes match records, one row per competitor-match
(Fighter, Opponent, W/L, Method, Competition, Weight, Stage, Year).

Modules, in pipeline order:
  config      every analysis choice as a named setting (with reset())
  cleaning    weight labels -> kg; match results -> submission / decision,
              submission family and specific technique
  sample      25 outcomes (submission wins and losses, by family and technique);
              each competitor's weight trajectory: never moved, moved up or down
              once, or the first clean move of a multi-mover; competitor-year panel
              with match-filtered placebo outcomes
  estimation  Callaway & Sant'Anna estimator for movers up and down separately,
              against never-movers and not-yet-movers; match-count weighting;
              competitor-clustered bootstrap shared across directions; naive
              two-way fixed effects for contrast
  plots       event-study charts
  pipeline    runs everything; splits each pair of estimates into
                direction effect  (up - down) / 2   depends on which way the competitor moved
                common shift      (up + down) / 2   comes with changing class at all
"""
from . import config
from .cleaning import classify_method, load_and_clean, weight_kg
from .estimation import CSDiD, boot_summary, twfe
from .pipeline import main
from .sample import SPECIFIC_SUBS, build_outcomes, build_panel, classify_trajectory
