# 0006. Under-25 income-tax exemption base case

Status: Accepted
Date: 2026-10-29
Sources: ticket 007, `docs/research/nz-under25-tax-evidence.md`

## Context

An exact individual calculator needs explicit policy rules. The statutory definition of employment income is broader than wages, so the policy must say which payments qualify. Tax rates, ACC levies, student-loan thresholds, and transfer rules vary by year and are separate from income tax.

## Decision

The first static scenario is:

- **Timing:** effective 1 April 2027, with no scheduled end date.
- **Eligibility:** assessed when PAYE salary or wages are paid. Income paid while the person is younger than 25 is exempt; income paid on or after the 25th birthday is not.
- **Qualifying income:** PAYE salary and wages only. Self-employment income is outside the base case and is a future scenario needing its own rules.
- **Calculation:** recompute annual income tax under the tax-year-specific marginal schedule after excluding qualifying income.
- **Unchanged items:** ACC earner levy, student-loan repayments, KiwiSaver, and other payroll deductions are kept separate and unchanged.
- **Transfers:** existing transfer and benefit income definitions apply, and disposable-income effects are shown only where those rules are explicitly implemented.
- **Financing:** government borrowing. Spending cuts and replacement taxes are separate scenarios.

## Consequences

- Rules are versioned by tax year; a future policy year uses the law then in force, not today's schedule by default. Current guidance is not the final 2027 rule set (for example, Working for Families changes effective 1 April 2027).
- Results are static incidence calculations. They estimate no behavioural or macroeconomic effects and make no claim about the fiscal cost of an enacted proposal.
- Alternative qualifying-income definitions, self-employment, other age rules, and other financing assumptions must be added as explicit scenarios, not inferred.
- Aggregate cost depends on adequate public data (ADR 0007).
