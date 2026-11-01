# NZ Economic Digital Twin

Vocabulary for the first vertical slice: point-in-time macro forecast backtests for New Zealand and a static under-25 income-tax exemption calculator. Identifiers in `code` are defined in `src/eco_model/contracts.py`. Decisions behind the terms are in `docs/adr/`.

## Language

### Time and information

**Forecast origin** (issue timestamp):
The UTC timestamp at which a forecast is issued (`ForecastRecord.origin`). Nothing published after it may influence the forecast.
_Avoid_: forecast date, as-of date (unqualified), cutoff

**Information set**:
The values, each tied to its vintage, that had been published at or before a forecast origin. `ObservationStore.as_of(series_id, as_of)` returns it and must never return a value published after `as_of`.
_Avoid_: training data, history (unqualified)

**Reference period**:
The calendar quarter a value describes (`Observation.ref_period`, a quarterly `pd.Period`). It is not when the value became known.
_Avoid_: date, period (unqualified), quarter-end date

**Publication time**:
When the source officially released a value (`Observation.published_at`, `SourceSnapshot.published_at`). It is taken from the dated release, never from an assumed lag; `None` means the release time is unverified.
_Avoid_: release lag, date

**Retrieval time**:
When this project downloaded a file (`SourceSnapshot.retrieved_at`, UTC). It is provenance only and never decides whether a value is in an information set.
_Avoid_: publication time, download date as a proxy for either

**Vintage**:
The set of values for a series as published in one release. A later release of the same series is a new vintage, and values for the same reference period may differ between vintages.
_Avoid_: version (reserved for parsed-data versions), latest (without naming the vintage)

**First release**:
The earliest-published value for a reference period (`ObservationStore.first_release`). It is what decision-makers first saw.
_Avoid_: initial estimate, advance estimate, actual

**Revised outcome**:
The value for a reference period taken from a specified later vintage (`ObservationStore.latest` at a stated extraction date, or another named vintage). It is scored separately from the first release, and the vintage is always named.
_Avoid_: final, true value, actual, outturn

### Evaluation design

**Real-time track** (`VintageTrack.REAL_TIME`):
Evaluation in which every input value at an origin is tied to an official publication available by that origin's timestamp. Only this track may be called real-time.
_Avoid_: live, vintage-safe (for any other track)

**Pseudo-out-of-sample track** (`VintageTrack.PSEUDO_OOS`; also the revised-data track):
Evaluation on current revised data truncated at each origin, used when historical vintages cannot be reconstructed. It leaves out the effect of data revisions, is labelled with its vintage limitation, and is never pooled with the real-time track.
_Avoid_: real-time, pseudo-real-time, historical vintage backtest

**Common origin**:
An origin issued after the latest of the three target releases for the shared reference quarter, so all targets have the same last observed quarter.
_Avoid_: shared date, synchronised origin

**Operational origin**:
An origin set per series from that series' own latest available observation. Its scores are not pooled with common-origin scores because they measure a different forecast task.
_Avoid_: real-world origin, live origin

**Horizon**:
The number of quarters ahead, `h` in `HORIZONS = (1, 4, 8)`, counted from a target's last observed quarter (`ForecastRecord.last_observed`). The quarter being forecast is stored explicitly as `ForecastRecord.target_period` and never inferred from row order.
_Avoid_: short/medium/long term, h-step lag

**Ragged edge**:
The state at an origin in which series end at different quarters because they are released at different times. It appears as NaN in the trailing rows of the `history` frame passed to `Forecaster.forecast`.
_Avoid_: missing data (unqualified), unbalanced panel

### Targets

**Target**:
A forecast variable in `TARGETS`: `GDP_GROWTH` (`gdp_growth_qoq_pct`), quarter-on-quarter, non-annualised percentage change in seasonally adjusted chain-volume real GDP; `CPI_INFLATION` (`cpi_inflation_yoy_pct`), year-on-year percentage change in the all-groups CPI index; `UNEMPLOYMENT` (`unemployment_rate_sa_pct`), the seasonally adjusted HLFS unemployment rate in percentage points.
_Avoid_: annualised GDP growth, quarterly CPI inflation, "the economy"

**Raw series** (`RAW_SERIES`):
A source series as published, in levels (`RAW_GDP_LEVEL`, `RAW_CPI_INDEX`, `RAW_UNEMPLOYMENT`), from which a target is derived by `transforms.to_targets`.
_Avoid_: raw data (unqualified), target (for a level)

### Methods and ensembles

**Persistence benchmark**:
The forecast equal to the latest observed value of the target, carried forward unchanged to every horizon.
_Avoid_: naive forecast, random walk (unless the level representation is stated)

**Historical-mean baseline**:
The mean of the target estimated from data in the information set. It is a reference comparator named in the validation plan, not an ensemble constituent.
_Avoid_: long-run average, trend

**Univariate method**:
One autoregressive or state-space model per target, fitted independently at each origin.
_Avoid_: AR model (when the state-space form is meant)

**Compact VAR**:
A small reduced-form vector autoregression on the three targets jointly, subject to data and stability diagnostics. It is a forecasting device and has no structural or causal interpretation.
_Avoid_: SVAR, structural model, macro model

**Equal-weight ensemble**:
The simple average of the persistence, univariate, and compact VAR forecasts. It is the primary combination baseline.
_Avoid_: naive ensemble, consensus

**Performance-weighted ensemble**:
A combination whose nonnegative weights sum to one, set separately per target and horizon from the most recent 20 to 40 prior eligible errors (`MIN_ERRORS_FOR_WEIGHTS`, `MAX_ERRORS_FOR_WEIGHTS`) and frozen before issuance (`ForecastRecord.weights`). With fewer than 20 errors it uses equal weights and is marked unavailable for that cell. It is a regularised comparator, not an optimal or causal weighting.
_Avoid_: optimal ensemble, learned ensemble, best-model selection

### Uncertainty

**Empirical predictive interval**:
An interval built by adding quantiles of prior out-of-sample errors for the same target, horizon, and track to the point forecast (`ForecastRecord.quantiles`). Levels are `INTERVAL_LEVELS`; 50% and 80% need at least 20 prior errors (`MIN_ERRORS_50_80`), 95% at least 40 (`MIN_ERRORS_95`), otherwise the interval is unavailable rather than extrapolated.
_Avoid_: confidence interval, credible interval, error bar

**Coverage**:
The share of realised outcomes that fall inside an interval, reported with interval width and error counts. It is an empirical diagnostic, not a probability guarantee, because errors are dependent, samples are short, and multi-step errors overlap.
_Avoid_: accuracy of the interval, probability of being right

### Provenance and value kinds

**Source snapshot** (`SourceSnapshot`):
An immutable, retrieved source file kept unchanged with its URL, retrieval time, publication time, checksum (`snapshot_id` is the SHA-256 of the file bytes), media type, and licence. Later downloads never overwrite it.
_Avoid_: latest download, cache, dump

**Observed / imputed / estimated / simulated** (`ValueKind`):
Observed values are published by a source as measured. Imputed values fill a missing measurement by a stated rule. Estimated values are inferred statistically from observed data. Simulated values come from applying assumed rules or a scenario. The four are never relabelled as one another, and household observations are never invented.
_Avoid_: actual, real data, synthetic data (unless simulated is meant)

### Tax scenario

**Qualifying income**:
PAYE salary and wages paid before the recipient's 25th birthday, from 1 April 2027. Self-employment income, ACC earner levy, student-loan repayments, KiwiSaver, and other payroll deductions are not qualifying and stay unchanged.
_Avoid_: employment income (the statutory term is broader), taxable income, under-25 income

**Exemption scenario**:
The base case in which qualifying income is excluded from annual income-tax liability. It starts 1 April 2027 with no end date, assesses eligibility when the income is paid, and assumes government borrowing as the financing.
_Avoid_: policy, reform, the proposal

**Static incidence calculation**:
Annual income tax recomputed under the tax-year-specific marginal schedule after removing qualifying income: baseline tax minus policy tax for the same inputs. It holds behaviour, wages, employment, and the macroeconomy fixed.
_Avoid_: impact, effect, simulation of the economy

**Aggregate revenue estimate**:
A national revenue change obtained by weighting individual static results over a population. It requires adequate joint public data (age, qualifying earnings, other taxable income) plus documented assumptions and uncertainty.
_Avoid_: cost (unqualified), saving, fiscal impact

**Not estimable**:
The reported status of the aggregate revenue estimate when public aggregates lack the needed joint distribution. It comes with a statement of the missing cross-tabulation and never with a point value or a data-only interval.
_Avoid_: zero, unknown, TBD

### Claims

**Forecast accuracy**:
How well a forecast predicted a specified published macro outcome, given the information set at its origin. It is scored with the point and probabilistic measures in the validation plan.
_Avoid_: model validity, model validation

**Causal policy effect**:
The difference between an outcome under a policy and a credible no-policy counterfactual. Neither forecast accuracy nor ensemble weights validate it, and it is not identified by this slice.
_Avoid_: forecast of the policy, policy impact on GDP

## Wording rules

- Say "first release" or "revised outcome (vintage named)", never "final" or "actual" GDP.
- Say "pseudo-out-of-sample" or "revised-data" for any run not built on dated historical vintages; "real-time" is reserved for the real-time track.
- Say "predictive interval" and "coverage", never "confidence interval" or "accuracy percentage".
- Say "static incidence" or "individual disposable-income change" for tax results; reserve "effect" for causal claims.
