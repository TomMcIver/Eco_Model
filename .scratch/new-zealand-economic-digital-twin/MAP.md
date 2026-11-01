# New Zealand Economic Digital Twin: First Reproducible Vertical Slice

## Destination

Produce the seven initial research and design documents plus a reproducible first vertical slice that ingests verified public New Zealand data, backtests at least two forecasting methods for quarterly real GDP growth, CPI inflation, and unemployment at 1, 4, and 8 quarters, compares equal and performance-weighted ensembles, reports predictive uncertainty and limitations, and calculates the static income-tax exemption scenario for individuals and—only where public data supports it—aggregate revenue impacts. This slice is not a validated causal policy engine.

## Notes

- This effort includes research, architecture, and implementation because the user explicitly requested the first vertical slice.
- Preserve the user's distinctions among observed, imputed, estimated, and simulated values. Never invent household observations or aggregate tax-cost estimates.
- Use source-backed public NZ data; do not assume access to Stats NZ IDI or other restricted microdata.
- Target NZ. International evidence may inform later methods only when institutional differences and transfer diagnostics are explicit.
- Use DuckDB and Parquet initially, retaining source files, dataset versions, retrieval and publication times, revisions, and provenance. Backtests must be point-in-time safe.
- The configured issue tracker is GitHub, but `gh auth status` reports invalid saved credentials. Per the user's instruction, this local map is the working ledger until GitHub authentication is restored; do not change the configured tracker or attempt GitHub writes meanwhile.
- Environment inspection found Python 3.12.13 and 3.11.15 managed by `uv`. The `python` command is a Windows Store alias, the `uv` default cache path is inaccessible in this sandbox, and the Docker daemon is unavailable. Use an explicit Python runtime and a workspace-local cache if needed.

## Decisions so far

- [Choose initial forecast targets and horizons](tickets/DEC-001-forecast-targets.md): Quarterly real GDP growth, CPI inflation, and unemployment at 1, 4, and 8 quarters; allow additional indicators and arbitrary horizons in the architecture.
- [Define first static tax-slice outputs](tickets/DEC-002-tax-outputs.md): Calculate exact individual disposable-income changes under explicit rules and estimate aggregate revenue only where public distributions support transparent assumptions and uncertainty; otherwise report the limitation.
- [Choose the initial research data store](tickets/DEC-003-data-store.md): Use DuckDB and Parquet with versioned datasets, original files, timestamps, publication vintages, revision history, full provenance, and point-in-time backtests.
- [Research model families and candidate first-slice methods](tickets/001-model-landscape.md): Start with a simple benchmark, univariate autoregressive/state-space method, and small reduced-form VAR; predictive validity and causal identification are distinct.
- [Research public NZ data and vintages](tickets/002-nz-data-catalog.md): Public official series and useful aggregates exist, but release/vintage coverage varies; restricted IDI is not public, and a sufficient recurring joint age-under-25 qualifying-income distribution was not verified.
- [Research under-25 tax rules and aggregate costing evidence](tickets/003-tax-policy-evidence.md): Exact individual effects require explicit eligibility and interactions; do not report an aggregate point cost without a suitable joint distribution or transparent bounded method.
- [Research point-in-time macro forecast evaluation](tickets/004-point-in-time-validation.md): Use rolling-origin information sets and separate first-release from revised outcomes; disclose gaps where machine-readable historical vintages are unavailable.
- [Select first-slice target definitions and forecast methods](tickets/006-forecast-contract.md): Use quarter-over-quarter non-annualized real GDP growth, year-over-year CPI inflation, and the seasonally adjusted HLFS unemployment rate; compare persistence, univariate autoregressive/state-space, and compact VAR methods.
- [Specify the under-25 income-tax exemption base case](tickets/007-tax-policy-spec.md): Start 1 April 2027; exempt PAYE salary and wages paid before age 25; keep other payroll/transfer rules separate and use borrowing as the base financing assumption.
- [Inspect public income tables for aggregate exemption-cost feasibility](tickets/008-tax-cost-data-feasibility.md): No-go for a point estimate or data-only uncertainty interval from the verified public marginals; exact workbook schemas remain unverified, and aggregate revenue is not estimable pending adequate joint data.
- [Choose forecast source-of-record and vintage policy](tickets/DEC-004-forecast-data-sources.md): Use official Stats NZ quarterly target series, immutable dated release snapshots, and separate strict real-time from pseudo-out-of-sample evaluation when complete historical vintages are unavailable.
- [Choose forecast uncertainty and ensemble-weighting rules](tickets/DEC-005-forecast-uncertainty-ensembles.md): Use equal weights as the baseline, regularized nonnegative past-error weights only with at least 20 prior errors per target/horizon, and empirical predictive intervals only when minimum history supports their tails.

## Not yet specified

- The compatible model result contract, baseline-state schema, accounting constraints, and reproducible experiment/evaluation artifacts.
- Exact statutory treatment and input requirements for employment income, self-employment, tax brackets, ACC levies, student loans, and transfers.
- How to structure later causal evaluation, regional coverage, international transfer, microsimulation, and adaptive ensembles after the first slice is evaluated.
- How to represent aggregate tax-cost uncertainty if the public sources lack a joint under-25 qualifying-income distribution.

## Out of scope

- Claiming that forecast accuracy validates causal policy effects.
- Treating restricted Stats NZ microdata as publicly accessible or fabricating household-level observations.
- Building a comprehensive national or regional digital twin in the first vertical slice.


