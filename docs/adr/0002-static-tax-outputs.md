# 0002. Static tax outputs: exact individual results, aggregate only on evidence

Status: Accepted
Date: 2026-10-29
Sources: DEC-002

## Context

The tax slice could report individual disposable-income changes, aggregate government revenue impacts, or both. Aggregate costing depends on public distributions that may not exist, and restricted microdata (Stats NZ IDI) is not available to the project.

## Decision

Implement both outputs under different evidence thresholds:

- Individual calculations must be exact under explicitly specified tax rules.
- Aggregate revenue estimates are produced only if public NZ income, employment, and tax data support them. They then carry uncertainty intervals and documented assumptions.
- Otherwise the system reports the limitation. It does not assume access to restricted microdata or invent figures.

## Consequences

- The calculator is a static incidence calculation. It estimates no behavioural, labour-market, or macroeconomic response and is not a causal policy engine.
- Aggregate output has two legitimate states: an estimate with stated assumptions and uncertainty, or "not estimable" with the missing data named.
- Observed, imputed, estimated, and simulated values stay distinguishable (`ValueKind`). No household-level observations are fabricated.
- The evidence threshold was later tested against the actual public tables; see ADR 0007.
- The scenario rules for the individual calculator are in ADR 0006.
