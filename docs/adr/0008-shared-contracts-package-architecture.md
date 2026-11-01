# 0008. Shared contracts module with independent packages

Status: Accepted
Date: 2026-10-29
Sources: `src/eco_model/contracts.py`, `pyproject.toml`

## Context

The slice has four separable concerns: ingesting and serving point-in-time data, forecasting methods, rolling-origin backtesting, and the static tax calculator. They are built and tested independently, and the point-in-time rules in ADR 0003 and ADR 0004 must hold at every boundary between them.

## Decision

Put every cross-package type in one module, `src/eco_model/contracts.py`, and keep the four packages independent of each other:

- `eco_model.data` implements the `ObservationStore` protocol and produces `SourceSnapshot` and `Observation` records.
- `eco_model.models` implements the `Forecaster` protocol: fitted afresh at each origin, reading only the `history` it is given, and deterministic for a given `seed`.
- `eco_model.backtest` issues `ForecastRecord`s per `VintageTrack`, using the store and forecasters only through those protocols.
- `eco_model.tax` implements the static calculator and shares no forecasting code.

Each of these packages depends only on `contracts`. The contracts module also holds the shared constants (targets, raw series, `HORIZONS`, the ADR 0005 thresholds), `ValueKind`, and `VintageTrack`. `eco_model.transforms` (raw levels to targets) is a pure helper that depends only on `contracts`. The `eco-model` command-line entry point (`eco_model.cli:main`) is the one place that composes the packages.

## Consequences

- A method, data source, or backtest driver can be replaced or tested alone, with tests mirrored under `tests/{data,models,backtest,tax}`.
- `contracts.py` is the coupling point. Per its own docstring, change it only with a matching ADR note, since every package depends on it.
- Leakage control is structural: models see only the `history` frame, and the store returns only values published by the requested time.
- Sharing logic between packages means promoting it into `contracts` or a pure helper, never importing one package from another.
