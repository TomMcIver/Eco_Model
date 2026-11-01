"""Point-in-time backtest and evaluation layer (VALIDATION_PLAN, DEC-004, DEC-005)."""

from eco_model.backtest.availability import StoreAvailability
from eco_model.backtest.infoset import InsufficientDataError, LeakageError, build_infoset
from eco_model.backtest.metrics import compute_metrics, revision_sensitivity
from eco_model.backtest.origins import origin_schedule, split_schedule
from eco_model.backtest.report import write_report
from eco_model.backtest.runner import run_backtest

__all__ = [
    "InsufficientDataError", "LeakageError", "StoreAvailability", "build_infoset",
    "compute_metrics", "origin_schedule", "revision_sensitivity", "run_backtest",
    "split_schedule", "write_report",
]
