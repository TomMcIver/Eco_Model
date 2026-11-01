# 0005. Forecast uncertainty and ensemble weighting

Status: Accepted
Date: 2026-10-29
Sources: DEC-005, `VALIDATION_PLAN.md`

## Context

Model errors are correlated and rolling-origin histories are short. Estimated combination weights add sampling error, so equal weights are hard to beat, and ordinary interval formulas rest on assumptions the data cannot support.

## Decision

- **Primary baseline:** the equal-weight average of the persistence, univariate, and compact VAR forecasts. Every constituent is reported alongside both ensemble variants.
- **Performance weights:** estimated per target and horizon from errors of prior eligible origins on the same vintage track, using at most the latest 40 (`MAX_ERRORS_FOR_WEIGHTS`). With fewer than 20 (`MIN_ERRORS_FOR_WEIGHTS`), use equal weights and mark performance weighting unavailable for that cell.
- **Weight rule:** shrink the error covariance toward its diagonal with a documented estimator. Choose nonnegative weights summing to one that minimise estimated combination-error variance plus a penalty toward equal weights, with penalty scale `trace(Sigma) / M` (`M` = number of methods). Freeze weights before each forecast is issued.
- **Intervals:** add quantiles of prior out-of-sample errors for that target, horizon, and track to the point forecast. Publish 50% and 80% intervals with at least 20 errors (`MIN_ERRORS_50_80`) and 95% only with at least 40 (`MIN_ERRORS_95`); otherwise mark them unavailable. Keep first-release and revised-outcome error pools separate.
- **Coverage and metrics:** treat coverage as an empirical diagnostic reported with counts and width. Use time-block resampling for uncertainty in aggregate metrics, disclosing the block rule and effective sample.
- Freeze these choices before the final evaluation interval and report sensitivity to equal weights and to the history window. Do not tune on final outcomes.

## Consequences

- Early origins have no performance-weighted or tail-interval output by design; the gaps are shown, not filled.
- The weights are a transparent regularised comparator, not optimal or causal weights.
- Intervals describe predictive error for observed macro outcomes and are not policy counterfactuals.
