# Eco_Model: NZ economic digital twin, first vertical slice

A reproducible first slice of a New Zealand economic digital twin. It has two parts:

1. **Point-in-time macro forecast backtests.** Quarterly real GDP growth, CPI inflation, and the unemployment rate are forecast 1, 4, and 8 quarters ahead from public Stats NZ data. Three methods (a persistence benchmark, a univariate autoregressive/state-space model, and a compact VAR), an equal-weight ensemble, and a performance-weighted ensemble are compared with empirical predictive intervals and coverage diagnostics, using only information published by each forecast origin.
2. **A static income-tax calculator** for a proposed exemption of PAYE salary and wages for people under 25. It gives exact individual results. Aggregate revenue is reported only where public data support it, and otherwise as "not estimable".

No backtest results are claimed in this repository until they are produced by the code and reported with their vintage standard.

## Non-goals

- **Not a causal policy engine.** Static tax results ignore behavioural and macroeconomic responses, and forecast accuracy does not validate any policy effect.
- **No restricted microdata.** Stats NZ IDI and other restricted data are not used, and household observations are never invented.
- **No fabricated aggregates.** Where public data cannot identify an aggregate (for example the exemption's national revenue cost), the output says so and names the missing data (see [ADR 0007](docs/adr/0007-aggregate-tax-cost-not-estimable.md)).
- **Not a comprehensive national or regional twin.** Larger model families (DSGE, CGE, agent-based, microsimulation) are deferred.

## Layout

```
src/eco_model/
  contracts.py   shared types, protocols, and constants; the only coupling point
  transforms.py  raw published levels -> forecast targets
  data/          ingest official releases, keep snapshots, serve point-in-time reads
  models/        forecasting methods (persistence, univariate, compact VAR)
  backtest/      rolling-origin evaluation, ensembles, intervals, scoring
  tax/           static under-25 exemption calculator
tests/           mirrors src/eco_model (tests/{data,models,backtest,tax})
data/            local store (git-ignored): raw snapshots and eco_model.duckdb
docs/adr/        architecture decision records
docs/research/   tax-rule and tax-cost data research notes
```

The `data`, `models`, `backtest`, and `tax` packages depend only on `contracts` ([ADR 0008](docs/adr/0008-shared-contracts-package-architecture.md)).

## Setup

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12 or 3.13. Use a workspace-local uv cache if the default cache path is not writable (as in some sandboxes).

PowerShell:

```powershell
$env:UV_CACHE_DIR = ".uv-cache"
uv sync
uv run pytest
```

POSIX shell:

```sh
export UV_CACHE_DIR=.uv-cache
uv sync
uv run pytest
```

Tests marked `network` need internet access to official sources; deselect them with `uv run pytest -m "not network"`.

## Commands

These are being built; the exact subcommands and options are defined by the code. Run `uv run eco-model --help` for the current interface.

| Purpose | Command |
| --- | --- |
| Ingest Stats NZ data into `data/eco_model.duckdb` | `uv run python -m eco_model.data.ingest` |
| Run forecast backtests | `uv run eco-model backtest ...` (see `eco-model --help`) |
| Run the static tax calculation | `uv run eco-model tax ...` (see `eco-model --help`) |

## Documentation

- [GLOSSARY.md](GLOSSARY.md): domain vocabulary (forecast origin, vintage, first release vs revised outcome, real-time vs pseudo-out-of-sample, and others).
- [docs/adr/](docs/adr/): decisions on [targets and horizons](docs/adr/0001-forecast-targets-and-horizons.md), [static tax outputs](docs/adr/0002-static-tax-outputs.md), [data store and provenance](docs/adr/0003-duckdb-parquet-data-store.md), [source and vintage policy](docs/adr/0004-forecast-source-and-vintage-policy.md), [uncertainty and ensembles](docs/adr/0005-uncertainty-and-ensemble-weighting.md), [exemption base case](docs/adr/0006-under-25-exemption-base-case.md), [aggregate cost not estimable](docs/adr/0007-aggregate-tax-cost-not-estimable.md), and [package architecture](docs/adr/0008-shared-contracts-package-architecture.md).
- [RESEARCH.md](RESEARCH.md): model families and frameworks, and the candidate first-slice method set.
- [DATA_CATALOG.md](DATA_CATALOG.md): public NZ data sources, access, licensing, and vintage availability.
- [VALIDATION_PLAN.md](VALIDATION_PLAN.md): point-in-time rolling-origin protocol, scoring, and uncertainty calibration.
- [docs/research/nz-under25-tax-evidence.md](docs/research/nz-under25-tax-evidence.md): tax rules and public costing evidence for the under-25 exemption.
- [docs/research/nz-tax-cost-data-feasibility.md](docs/research/nz-tax-cost-data-feasibility.md): why aggregate costing is a no-go from the verified public tables.

## Work tracking

The project map and its tickets are kept as a local ledger in [`.scratch/new-zealand-economic-digital-twin/`](.scratch/new-zealand-economic-digital-twin/MAP.md) (`MAP.md` and `tickets/`). The configured tracker is GitHub Issues, but publishing the map is pending: `gh auth status` still reports invalid saved credentials (ticket 005, blocked). Until authentication is restored, the local ledger is the working record; list open tickets with:

```powershell
rg -l '^Status: (open|blocked)' .scratch/new-zealand-economic-digital-twin/tickets
```
