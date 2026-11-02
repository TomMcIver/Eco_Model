"""Rolling-origin backtest runner: individual methods, ensembles, intervals, outcomes.

Pipeline per track (never pooled across tracks, DEC-004):

1. For each origin build the point-in-time information set and ask every
   forecaster for {(target, h): point}; record ``last_observed`` and the
   explicit ``target_period = last_observed + h``.
2. Attach first-release and revised outcomes plus when the outcome became known.
3. Add ``ensemble_equal`` / ``ensemble_perf`` with weights frozen at issuance.
4. Add empirical quantiles for every method from errors known at issuance.

Reproducibility metadata (seed, methods, code version, run id) is in ``attrs``.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Mapping, Sequence

import pandas as pd

from eco_model.backtest.availability import (
    AssumedLagDays,
    AvailableAt,
    StoreAvailability,
    make_resolver,
    to_utc,
)
from eco_model.backtest.ensembles import (
    EnsembleFns,
    QuantileFn,
    add_intervals,
    ensemble_rows,
    error_column,
    load_default_ensemble_fns,
    load_default_quantile_fn,
)
from eco_model.backtest.infoset import InsufficientDataError, build_infoset
from eco_model.backtest.outcomes import attach_outcomes, build_outcome_tables
from eco_model.contracts import HORIZONS, Forecaster, ObservationStore, VintageTrack

logger = logging.getLogger(__name__)

DEFAULT_CODE_VERSION = "0.1.0"
RECORD_COLUMNS = (
    "track", "origin", "method", "target", "horizon", "last_observed",
    "target_period", "point", "weights", "notes",
)


def code_version() -> str:
    import eco_model

    return str(getattr(eco_model, "__version__", DEFAULT_CODE_VERSION))


def _normalise_origins(origins) -> list[tuple[pd.Timestamp, pd.Period | None]]:
    """Accept a sequence of datetimes or a schedule frame with origin[, ref_quarter]."""
    if isinstance(origins, pd.DataFrame):
        cutoffs = origins["ref_quarter"] if "ref_quarter" in origins else [None] * len(origins)
        pairs = [(to_utc(o), c) for o, c in zip(origins["origin"], cutoffs)]
    else:
        pairs = [(to_utc(o), None) for o in origins]
    return sorted(dict(pairs).items(), key=lambda kv: kv[0])


def _forecast_rows(info, forecaster: Forecaster, horizons, seed: int) -> list[dict]:
    history = info.targets.copy()
    points = forecaster.forecast(history, list(horizons), seed=seed)
    rows = []
    for (target, horizon), point in sorted(points.items()):
        last = info.targets[target].last_valid_index() if target in info.targets else None
        if last is None:
            continue
        rows.append({
            "track": info.track.value, "origin": info.origin, "method": forecaster.name,
            "target": target, "horizon": int(horizon), "last_observed": last,
            "target_period": last + int(horizon), "point": float(point),
            "weights": None, "notes": info.notes,
        })
    return rows


def _issue_all(store, track, schedule, forecasters, horizons, seed, available_at, lag, log):
    rows: list[dict] = []
    for origin, cutoff in schedule:
        try:
            info = build_infoset(store, track, origin, available_at=available_at,
                                 assumed_lag_days=lag, cutoff=cutoff)
        except InsufficientDataError as exc:
            log["skipped_origins"].append({"origin": origin.isoformat(), "reason": str(exc)})
            continue
        for forecaster in forecasters:
            try:
                rows.extend(_forecast_rows(info, forecaster, horizons, seed))
            except Exception as exc:  # recorded, never silently dropped
                logger.warning("forecaster %s failed at %s: %s", forecaster.name, origin, exc)
                log["failures"].append({"origin": origin.isoformat(),
                                        "method": forecaster.name, "error": repr(exc)})
    return pd.DataFrame(rows, columns=list(RECORD_COLUMNS))


def run_id_for(track: VintageTrack, schedule, methods, horizons, seed: int, version: str,
               data_state: Mapping[str, str] | None = None) -> str:
    payload = json.dumps({
        "track": track.value, "origins": [o.isoformat() for o, _ in schedule],
        "methods": list(methods), "horizons": list(horizons), "seed": seed, "version": version,
        "data_state": dict(data_state or {}),
    }, sort_keys=True)
    return f"{track.value}-{hashlib.sha256(payload.encode()).hexdigest()[:12]}"


def run_backtest(
    store: ObservationStore,
    track: VintageTrack,
    origins: Sequence[datetime] | pd.DataFrame,
    forecasters: Sequence[Forecaster],
    horizons: Sequence[int] = HORIZONS,
    available_at: AvailableAt | None = None,
    seed: int = 0,
    *,
    assumed_lag_days: AssumedLagDays | None = None,
    ensemble_fns: EnsembleFns | None = None,
    quantile_fn: QuantileFn | None = None,
) -> pd.DataFrame:
    """One row per origin x method x target x horizon, incl. ensembles, intervals, outcomes.

    ``available_at`` defaults to verified store release times; ``assumed_lag_days``
    is only a labelled fallback. ``ensemble_fns`` / ``quantile_fn`` default to
    ``eco_model.models`` (imported lazily) and can be injected for testing.
    """
    track = VintageTrack(track)
    fns = ensemble_fns or load_default_ensemble_fns()
    qfn = quantile_fn or load_default_quantile_fn()
    schedule = _normalise_origins(origins)
    log: dict[str, list] = {"skipped_origins": [], "failures": []}
    issued = _issue_all(store, track, schedule, forecasters, horizons, seed,
                        available_at, assumed_lag_days, log)
    resolver = make_resolver(available_at or StoreAvailability(store), assumed_lag_days)
    tables = build_outcome_tables(store)
    err_col = error_column(track)
    base = attach_outcomes(issued, tables, resolver)
    ensembles = ensemble_rows(base, fns, err_col)
    if not ensembles.empty:
        base = pd.concat([base, attach_outcomes(ensembles, tables, resolver)], ignore_index=True)
    result = add_intervals(base, qfn, err_col) if not base.empty else base
    result = result.sort_values(["origin", "target", "horizon", "method"]).reset_index(drop=True)
    version = code_version()
    methods = [f.name for f in forecasters] + ["ensemble_equal", "ensemble_perf"]
    result.attrs = {
        "run_id": run_id_for(track, schedule, methods, horizons, seed, version,
                             {k: str(v) for k, v in tables.revised_as_of.items()}),
        "track": track.value, "seed": seed, "code_version": version, "methods": methods,
        "horizons": list(horizons), "interval_error_pool": err_col,
        "revised_as_of": dict(tables.revised_as_of),
        "created_at": datetime.now(timezone.utc).isoformat(), **log,
    }
    return result
