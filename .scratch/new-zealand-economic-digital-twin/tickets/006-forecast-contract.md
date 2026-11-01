# Select first-slice target definitions and forecast methods

Status: closed
Type: grilling
Assignee: Codex
Blocked by: 001-model-landscape.md; 002-nz-data-catalog.md; 004-point-in-time-validation.md

## Question

Which precise quarterly target transformations and candidate model set should the first point-in-time backtest implement?

Research supports a simple benchmark, a univariate autoregressive/state-space model, and a compact reduced-form VAR, but the CPI inflation measure and scale of the target outputs still need to be made explicit.

## Recommended answer

- GDP: quarter-over-quarter percentage growth in seasonally adjusted real GDP, not annualized.
- CPI: year-over-year percentage change in the CPI index, matching the familiar inflation rate.
- Unemployment: seasonally adjusted HLFS unemployment rate in percentage points.
- Compare a persistence benchmark, one univariate autoregressive/state-space method per target, and a compact three-variable reduced-form VAR, subject to data and stability diagnostics. Compare every method at 1, 4, and 8 quarters using the point-in-time rolling-origin protocol.

This specifies predictive targets and does not confer causal interpretation on any forecast.

## Resolution

Use quarter-over-quarter, non-annualized percentage growth in seasonally adjusted real GDP; year-over-year percentage change in CPI; and the seasonally adjusted HLFS unemployment rate in percentage points. Compare a persistence benchmark, one univariate autoregressive/state-space model per target, and a compact three-variable reduced-form VAR at 1, 4, and 8 quarters using point-in-time rolling-origin evaluation. Apply data and stability diagnostics; report forecast and causal-policy claims separately.

