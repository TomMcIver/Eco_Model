# Research model families and candidate first-slice methods

Status: closed
Type: research
Blocked by: none

## Question

What does high-quality research and primary-source documentation establish about the mathematical foundations, inputs, outputs, data requirements, identification assumptions, computational demands, suitable horizons, strengths, limitations, validation evidence, NZ suitability, and integration contracts of the requested model families and frameworks? Recommend at least two complementary, independently testable forecasting methods for the first quarterly target set and compare simple ensemble baselines, accounting for correlated errors. Do not implement the full model catalogue.

Cover DSGE, CGE, structural macroeconometric, VAR/SVAR/BVAR, state-space/Kalman, agent-based, tax-benefit microsimulation, input-output, system dynamics, Bayesian hierarchical, Gaussian-process, causal inference/evaluation, and ML forecasting families; assess OpenFisca, Dynare, PyMC, NumPyro, statsmodels, linearmodels, JAX, and relevant NZ modelling work. Distinguish forecast performance evidence from causal-policy validation.

## Deliverable

Write source-cited findings to `RESEARCH.md` in the repository root. Separate established evidence, assumptions, and hypotheses; identify limitations and a minimal set suitable for the first slice.

## Resolution

Research is recorded in [`RESEARCH.md`](../../../RESEARCH.md). Begin with a simple no-change or historical-mean benchmark, a univariate autoregressive/state-space method, and a small reduced-form VAR. Compare them independently before combining forecasts. Equal weighting is a sensible baseline; performance weighting must be learned from rolling out-of-sample errors and account for correlated model errors. NZSIM is relevant local precedent, but no verified open executable implementation or NZ accuracy evidence was established. Predictive performance does not establish causal policy validity.

