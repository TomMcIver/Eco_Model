"""Point-in-time data layer: immutable raw snapshots, DuckDB store, Stats NZ ingestion."""

from eco_model.data.statsnz_catalog import STATSNZ_SERIES, assumed_publication_lag_days
from eco_model.data.store import DuckDBObservationStore, ReleaseEntry

__all__ = [
    "DuckDBObservationStore",
    "ReleaseEntry",
    "STATSNZ_SERIES",
    "assumed_publication_lag_days",
]
