# 0007. Aggregate exemption cost is not estimable from public aggregates

Status: Accepted
Date: 2026-10-29
Sources: ticket 008, `docs/research/nz-tax-cost-data-feasibility.md`, ADR 0002

## Context

ADR 0002 permits an aggregate revenue estimate only if public data support it. Ticket 008 inspected the documented public Inland Revenue and Stats NZ tables. They give separate marginals: wage/salary counts and totals by income band, taxable income and tax by income band, age-specific median weekly wages, and household income statistics. No verified recurring public table jointly cross-classifies age, qualifying PAYE earnings, other taxable income, and tax liability. The tax schedule is nonlinear, so the total cannot be computed from the marginals without an independence assumption that no source supports. The IRD XLSX workbooks could not be retrieved, so worksheet-level contents remain unverified.

## Decision

No-go for an aggregate point estimate or a data-only uncertainty interval from the currently verified public tables. Implement the exact individual calculator, and report aggregate revenue as "not estimable from available public aggregates", naming the missing cross-tabulation. Do not synthesise household records or apply independence assumptions to the marginals.

## Consequences

- The tax package produces no aggregate figure for this scenario. Its output states the limitation and the missing data instead.
- Reopen the decision if inspecting the IRD workbooks in the ingestion environment, or a new release, supplies adequate joint data.
- If it is still missing, request a privacy-safe aggregate from IRD or Stats NZ: tax year; single-year age 15-24 (or the finest safe groups preserving the boundary); counts and total annual qualifying PAYE wages by band aligned to the tax thresholds; joint bands for other taxable income; ideally baseline tax and credits; and suppression and vintage metadata.
- If only grouped data are available, first specify the partial-identification problem and compute bounds from compatible joint constraints. Any such range is a scenario result conditional on stated assumptions, not a data-only interval or an official costing.
- Static results never imply a causal or behavioural policy effect.
