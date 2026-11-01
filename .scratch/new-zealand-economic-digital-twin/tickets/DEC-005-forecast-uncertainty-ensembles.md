# Choose forecast uncertainty and ensemble-weighting rules

Status: closed
Type: grilling
Blocked by: 001-model-landscape.md; 004-point-in-time-validation.md; 006-forecast-contract.md; DEC-004-forecast-data-sources.md

## Question

How should the first slice estimate forecast uncertainty and performance-weight ensemble forecasts when the model errors are correlated and the rolling-origin history is limited?

## Resolution

- Keep the equal-weight average of the persistence, univariate, and compact VAR forecasts as the primary combination baseline. Report every constituent method alongside both ensemble variants.
- Estimate performance weights separately for each target and horizon, using only errors from prior eligible rolling origins on the same target-vintage track. Use at most the most recent 40 eligible origin errors. With fewer than 20 available errors, use equal weights and mark performance weighting unavailable for that cell.
- Once the minimum history is available, estimate the error covariance from the common set of prior origin errors and shrink it toward its diagonal using a documented shrinkage estimator. Choose nonnegative weights summing to one by minimizing estimated combination-error variance plus a penalty toward equal weights. Set the penalty scale to `trace(Sigma) / M`, where `Sigma` is the shrunk error covariance and `M` is the number of constituent methods. Freeze weights before issuing each forecast. This is a transparent regularized comparator, not a claim of optimal or causal weights.
- For uncertainty, form an empirical predictive error distribution from prior out-of-sample errors for that target and horizon, using only errors available at issuance. Add those errors to the point forecast to produce predictive quantiles; report 50% and 80% intervals with at least 20 errors and a 95% interval only with at least 40. Otherwise mark the interval unavailable rather than extrapolating unsupported tails. Use the same vintage standard as the point forecast and keep first-release and revised-outcome residual pools separate.
- Treat interval coverage as an empirical diagnostic, not a guaranteed probability statement: quarterly errors are dependent, the sample is short, and rolling multi-step errors overlap. Report counts and interval width with coverage. Use time-block resampling for uncertainty around aggregate evaluation metrics, disclose the block rule and effective sample, and do not interpret those resamples as policy counterfactuals.
- Freeze these choices before the final evaluation interval. Report sensitivity to equal weights and to the stated history window; do not tune on final evaluation outcomes.

The uncertainty describes predictive errors for observed macro outcomes. Neither forecast accuracy nor ensemble weights validate a causal policy effect.
