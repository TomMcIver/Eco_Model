# 0001. Forecast targets, horizons, and first-slice methods

Status: Accepted
Date: 2026-10-29
Sources: DEC-001, ticket 006 (`.scratch/new-zealand-economic-digital-twin/tickets/`)

## Context

The first vertical slice needs a fixed set of outcomes, horizons, and candidate methods so backtests are comparable. Research (`RESEARCH.md`) supported a simple benchmark, a univariate autoregressive/state-space method, and a small reduced-form VAR. The CPI inflation measure and the scale of each target still had to be made explicit.

## Decision

Forecast three quarterly targets at horizons of 1, 4, and 8 quarters (`HORIZONS`):

- `GDP_GROWTH` (`gdp_growth_qoq_pct`): quarter-on-quarter percentage growth in seasonally adjusted real GDP, not annualised.
- `CPI_INFLATION` (`cpi_inflation_yoy_pct`): year-on-year percentage change in the all-groups CPI index.
- `UNEMPLOYMENT` (`unemployment_rate_sa_pct`): the seasonally adjusted HLFS unemployment rate, in percentage points.

Compare three methods at every target and horizon, from identical origins and information sets: a persistence benchmark, one univariate autoregressive/state-space model per target, and a compact three-variable reduced-form VAR, subject to data and stability diagnostics. The architecture must allow further indicators and arbitrary horizons later.

## Consequences

- Target definitions are frozen in `contracts.py` and `transforms.py`; changing one needs a new ADR.
- Forecast claims and causal-policy claims are reported separately. These targets give no causal interpretation to any forecast.
- If the VAR proves unstable or over-parameterised on short samples, the next candidate is a Minnesota-prior BVAR, researched explicitly rather than by silently shrinking the VAR (`RESEARCH.md`).
- `VALIDATION_PLAN.md` also names a historical-mean baseline as a reference comparator. It is not one of the three methods above and is not an ensemble constituent (ADR 0005).
- Larger model families (DSGE, CGE, agent-based, and similar) are deferred until a concrete use case and adequate data justify them.
