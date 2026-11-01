# Historical Forecast and Uncertainty Validation Plan

Status: research-backed protocol proposal; no model has been backtested yet.

## Purpose and scope

Evaluate forecasts for quarterly New Zealand real GDP growth, CPI inflation, and the unemployment rate at 1, 4, and 8 quarter horizons. This is forecast evaluation: it measures how well a forecast predicts a specified published outcome. It does not establish the causal effect of a policy. A policy effect requires a counterfactual for what would have happened without the policy and a design that supports that comparison.

The plan separates three things that can otherwise be conflated:

1. The information set available when a forecast was issued.
2. The outcome release first available after the target quarter.
3. Later revised estimates of that same outcome.

Stats NZ states that GDP estimates are revised as newer source data and annual benchmarks become available; routine quarterly GDP releases generally revise the previous quarter, while the September release typically revises eight quarters, and exceptional revisions can reach further back. Seasonal factors can also change as new observations are added. Consequently, a backtest using only today's revised series is not a real-time backtest. [Stats NZ macro-economic revisions policy](https://www.stats.govt.nz/corporate/revision-policy-macro-economic-statistics/), [Stats NZ National Accounts quarterly metadata](https://datainfoplus.stats.govt.nz/item/nz.govt.stats/9a9295f6-ce5c-4c71-8462-ba6dd01f4dc7/367)

Stats NZ's HLFS seasonal-adjusted estimates are revised as new quarterly data is added; population reweighting can also revise historic results. The CPI method page says its official decomposition is not revised, but CPI methodology, baskets, and weights do change over time. Treat that as a series-specific property to verify against release metadata, not as evidence that the full CPI history is immutable. [Stats NZ HLFS methods, 2025](https://www.stats.govt.nz/assets/Methods/Household-Labour-Force-Survey-sources-and-methods-2025/household-labour-force-survey-sources-and-methods-2025.pdf), [Stats NZ HLFS revision notes](https://www.stats.govt.nz/reports/household-labour-force-survey-population-reweight-september-2013september-2019-quarters/), [Stats NZ seasonal adjustment methods](https://www.stats.govt.nz/methods/seasonal-adjustment-in-stats-nz/), [Stats NZ CPI DataInfo+](https://datainfoplus.stats.govt.nz/Item/nz.govt.stats/8b0860b8-cf63-4f12-a578-8eed8ba69ac3)

## What historical evidence is available

- Stats NZ's GDP DataInfo+ releases include tables comparing previously published with updated quarterly GDP and expenditure-on-GDP movements. This is useful revision evidence, though a complete point-in-time archive/API for every series and release has not been established by this research ticket. [Stats NZ quarterly national accounts metadata](https://datainfoplus.stats.govt.nz/item/nz.govt.stats/5e99e77b-056e-4956-b8be-10a0cf3253b4/13)
- HLFS release pages report revisions to seasonal-adjusted estimates and document changes from seasonal adjustment, imputation, and population reweighting. Each quarterly release is a distinct potential vintage; retaining the source release files is necessary to recreate what users could see then. [Stats NZ HLFS revisions](https://www.stats.govt.nz/methods/household-labour-force-survey-revisions-to-labour-market-estimates/), [example release metadata](https://datainfoplus.stats.govt.nz/item/example.org/fe13c183-ddcd-45e4-991b-c8ebef8ed1ad)
- Stats NZ CPI quarterly release pages and DataInfo+ metadata provide an official release history, but this research has not confirmed a machine-readable vintage API or a complete archive of every historical table as originally published. Historical rebasing and methodology revisions need to be distinguished from revisions to published index observations. [Stats NZ CPI metadata](https://datainfoplus.stats.govt.nz/Item/nz.govt.stats/8b0860b8-cf63-4f12-a578-8eed8ba69ac3), [Stats NZ CPI release page](https://www.stats.govt.nz/indicators/consumers-price-index-cpi/)
- RBNZ publishes Monetary Policy Statements with quarterly forecast tables and provides past statements, which can support a published-forecaster comparator when target definitions, forecast dates, and available forecast horizons align. RBNZ's forecast-performance studies compare forecasts with statistical and private-bank alternatives and discuss forecast errors, bias, horizons, and GDP first releases versus later revised estimates. These are useful benchmarks and design precedents, not observations from the proposed models. [RBNZ past policy statements](https://www.rbnz.govt.nz/monetary-policy/monetary-policy-decisions), [RBNZ 2022 forecast evaluation](https://www.rbnz.govt.nz/en/hub/publications/bulletin/2022/rafimp-bulletin), [RBNZ post-COVID forecast evaluation](https://www.rbnz.govt.nz/research-and-publications/research/our-research-and-analysis/bulletins/2025/forecasting-performance-in-the-post-covid-19-disinflation-period)
- Stats NZ publishes a release calendar. Historical origin timestamps should be taken from the dated release itself, not reconstructed from the reference quarter or assumed publication lag. [Stats NZ release calendar](https://www.stats.govt.nz/release-calendar/)

**Vintage availability limitation:** the cited sources establish that revisions occur and that some historical first-versus-updated comparisons are documented. They do not establish complete downloadable real-time vintages for all three targets. Before claiming a real-time backtest, inventory archived release files and their publication timestamps. If only a current revised series is obtainable for some historical dates, classify those runs as revised-data or pseudo-real-time backtests and keep them separate from true real-time results. Start capturing immutable release snapshots prospectively.

## Forecast-origin and information-set protocol

1. **Use a recorded issue timestamp.** Each forecast record must store creation time in UTC, corresponding New Zealand release-calendar date/time, code commit, model version, dataset snapshot IDs, target definitions, assumptions, parameters, and random seed.
2. **Set quarterly origins consistently.** Use a fixed quarterly schedule after the latest of the three target releases for the prior common reference quarter. This ensures all target series have the same last observed reference quarter at issuance. Define horizons as the next 1, 4, or 8 quarterly observations after that common cutoff. Store the exact target quarter explicitly; never infer it later from row order.
3. **Enforce point-in-time retrieval.** A value can enter the origin's feature set only if its original publication timestamp is on or before the issue timestamp. Store both reference period and publication timestamp, plus the source's release/vintage identifier. Later downloads must not silently update an earlier snapshot.
4. **Fit transformations at each origin.** Scaling, imputation, seasonal adjustment, feature selection, model tuning, and hyperparameter selection must use only data in that origin's information set. Do not apply today's seasonal-adjustment factors or today's imputed/revised history to earlier origins. If a series' source publishes seasonally adjusted vintage values, use that vintage; otherwise seasonal adjustment must be re-estimated from the information set available then.
5. **Separate development from evaluation.** Choose training and tuning rules using rolling-origin validation within the development interval. Freeze a later contiguous evaluation interval, model specifications, transformations, scoring rules, and benchmark set before calculating final scores. Do not use evaluation outcomes to pick models, tune weights, or revise the protocol.

If a common origin after all target releases proves infeasible for long historical periods, publish two named protocols: (a) common-target origins based on the latest shared reference quarter, and (b) operational origins based on each series' latest available observation. Do not pool their scores as if they measure the same forecast task.

## Target definitions and scoring windows

Pre-register a canonical target definition per variable before backtesting. Recommended starting definitions are:

- **Real GDP growth:** Stats NZ's quarterly percentage change in seasonally adjusted chain-volume GDP, with the target reference quarter stored. Score the first published estimate and a later revised-estimate outcome separately.
- **CPI inflation:** the all-groups CPI annual percentage change for the target quarter, matching the headline official inflation concept. Also retain the CPI index vintage so an alternative quarter-to-quarter transformation can be audited if the modelling ticket selects it.
- **Unemployment:** Stats NZ's seasonally adjusted HLFS unemployment rate for the target quarter. Score the first published estimate and the later revised value separately when vintages are available.

The canonical definitions above are recommendations; transformations must be checked against source metadata and frozen in the architecture/math specification before model results are reported. CPI index methodology and weights change, so preserve base/weight metadata and do not splice incompatible definitions without a documented linking rule.

For each forecast, record the forecast for the specific target quarter and the corresponding target vintage. Report at least:

- **First-release score:** error relative to the first official release for the target period. This assesses the prediction against what decision-makers first observed.
- **Revised-outcome score:** error relative to a specified later vintage, such as the latest value frozen at evaluation-data release. State its extraction date and revision status. Do not label it “final” unless the source defines a final value.
- **Revision sensitivity:** difference between the first-release and revised-outcome scores, and the target revision itself. This matters especially for GDP; RBNZ's evaluation reports comparing short-horizon GDP forecasts to first release and longer-horizon forecasts to revised GDP, and notes upward GDP revisions. [RBNZ post-COVID forecast evaluation](https://www.rbnz.govt.nz/research-and-publications/research/our-research-and-analysis/bulletins/2025/forecasting-performance-in-the-post-covid-19-disinflation-period)

All models and baselines must be scored over the same origin/target pairs for a given variable and horizon. Publish the count of valid observations and exclusions for every cell. Do not compare a model's longer, easier sample with a benchmark's shorter sample.

## Baselines and ensemble evaluation

Include at least:

1. **No-change/random-walk baseline:** forecast the latest available level unchanged; for a growth/rate target this implies persistence in the target rate or zero growth if modelling the log level. Specify which representation is used.
2. **Historical-mean baseline:** forecast the mean target value estimated from data available at that origin.
3. **Seasonal-naive baseline** where seasonality remains in the chosen unadjusted target representation.

First compare each candidate model against these baselines. Then compare a simple equal-weight average and a performance-weighted combination. Keep the equal-weight average as the primary combination baseline. Estimate performance weights separately for each target and horizon, using only prior eligible rolling-origin errors on the same vintage track and common origin set. Use at most the latest 40 eligible errors. With fewer than 20 errors, fall back to equal weights and mark performance weighting unavailable. Otherwise estimate covariance from the common error set, shrink it toward its diagonal with a documented estimator, and choose nonnegative weights summing to one by minimizing estimated combination-error variance plus a penalty toward equal weights. Set the penalty scale to `trace(Sigma) / M`, where `Sigma` is the shrunk covariance and `M` is the number of methods. Freeze weights before issuing each forecast. This is a regularized comparator, not a claim of optimality. Report covariance and compare the weighted ensemble with the equal-weight combination, each method, and the simple baselines.

RBNZ's published evaluation compares its forecasts with statistical and private-sector forecasts and assesses bias, accuracy, horizon effects, and error correlations. Use that as a local evaluation precedent, not as an assumption that the proposed system should achieve the same performance. [RBNZ forecast evaluation](https://www.rbnz.govt.nz/en/hub/publications/bulletin/2022/rafimp-bulletin), [RBNZ post-COVID forecast evaluation](https://www.rbnz.govt.nz/research-and-publications/research/our-research-and-analysis/bulletins/2025/forecasting-performance-in-the-post-covid-19-disinflation-period)

## Metrics and uncertainty calibration

For each target and horizon, report:

- MAE and RMSE in the target's natural units.
- Mean signed error (bias), median absolute error, and a time plot of errors.
- Improvement or deterioration relative to each baseline, with the denominator and sign convention shown.
- Predictive quantiles from the empirical distribution of prior out-of-sample errors for that same target and horizon, added to the point forecast. Keep first-release and revised-outcome error pools separate. Report 50% and 80% intervals only with at least 20 prior errors, and a 95% interval only with at least 40; otherwise mark the interval unavailable.
- Empirical coverage and average width for available predeclared 50%, 80%, and 95% intervals; calibration plots by horizon and target. Treat these as diagnostics, not guaranteed probability statements: quarterly errors are dependent, the sample is short, and multi-step errors overlap.
- Forecast-origin counts and the distribution of errors across calm and high-volatility periods. Label crisis-period comparisons as descriptive if sample size is small.

Do not collapse these into one universal “accuracy percentage.” Point accuracy, bias, interval coverage, and interval sharpness answer different questions. Report metric uncertainty using time-block resampling that respects temporal dependence; state the block rule and effective sample size. Treat formal pairwise significance tests as secondary and disclose their assumptions. No values or performance claims should be filled in before running the backtest.

## Forecast evaluation versus causal policy evaluation

Forecast evaluation asks whether a model predicted the observed path given information available at forecast time. It can be measured for ordinary macroeconomic outcomes with point and probabilistic scores.

Causal policy evaluation asks whether the policy changed an outcome compared with a credible no-policy counterfactual. A good forecast of GDP, CPI, or unemployment does not identify that counterfactual. A policy simulation must therefore be kept separate from the forecasting leaderboard and must identify its estimand, treatment timing/exposure, comparison group or structural identification assumptions, confounders, uncertainty, and diagnostics. Appropriate methods may include difference-in-differences, synthetic controls, regression discontinuity, or instrumental variables only when their design assumptions are defensible for the specific policy and data. If no credible counterfactual exists, report the policy effect as unidentified and show assumption-driven sensitivity scenarios instead of presenting a forecast error as causal validation.

## Acceptance criteria for the first evaluation report

- Every forecast is reproducible from a saved model version, issue timestamp, parameters/seed, and immutable data snapshot.
- Historical feature sets contain no observations published after their issue timestamps; leakage checks fail closed.
- The point-in-time and revised-data tracks are explicitly distinguished; unavailable vintage history is reported, not silently imputed from current data.
- The three agreed targets and all 1/4/8 quarter horizons are scored against the same declared baselines on identical origin/target pairs.
- Equal-weight and past-performance-weighted ensembles are compared to constituent models and simple baselines.
- Point scores, bias, uncertainty calibration/coverage, interval widths, sample counts, and target revision sensitivity are reported.
- A frozen evaluation interval is not used for model or ensemble selection.
- The report says explicitly that forecast performance does not establish causal policy-effect accuracy.

