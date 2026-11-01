# Research point-in-time macro forecast evaluation

Status: closed
Type: research
Blocked by: none

## Question

What public historical forecast vintages and realized-data vintages exist for NZ GDP, CPI, and unemployment? Research primary-source data-release histories, national-statistics revision practices, and official/academic forecast archives. Recommend a rolling-origin design that prevents look-ahead bias at 1, 4, and 8 quarters, defines target transformations and scoring windows, and handles revised outcomes. Specify appropriate point/probabilistic scores, interval calibration, simple baselines, frozen evaluation windows, and uncertainty comparisons. Distinguish forecast evaluation from causal-policy evaluation and note what cannot be evaluated without independent counterfactual evidence.

## Deliverable

Write evidence and a recommended protocol to `VALIDATION_PLAN.md` in the repository root, with source citations and explicit gaps in vintage availability.

## Resolution

The source-cited protocol is in [`VALIDATION_PLAN.md`](../../../VALIDATION_PLAN.md). Use rolling-origin point-in-time forecasts for all agreed targets and horizons; retain forecast-date information sets, compare first-release and revised outcomes separately, and report point and probabilistic scores, interval coverage, calibration, and simple baselines. Complete machine-readable historical vintages are not established for every target, so each backtest must disclose which vintage standard it satisfies. Forecast evaluation remains separate from causal policy evaluation.

