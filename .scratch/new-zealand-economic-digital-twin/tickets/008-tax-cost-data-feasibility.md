# Inspect public income tables for aggregate exemption-cost feasibility

Status: closed
Type: research
Blocked by: 002-nz-data-catalog.md; 003-tax-policy-evidence.md

## Question

Do the actual downloadable, publicly accessible NZ income, employment, and tax tables contain enough joint age, income-source, income-band, and tax information to estimate aggregate revenue impacts of the agreed PAYE salary-and-wage exemption for under-25s? Inspect table schemas, age bands, coverage, units, suppression, vintages, and population definitions from Stats NZ and Inland Revenue. Determine whether public grouped data support a transparent estimate or defensible bounds; explain why marginal tables cannot identify a joint distribution without additional assumptions. If they do not, specify precisely which additional cross-tabulation would be needed and whether a grouped-data sensitivity analysis can avoid false precision. Do not synthesize empirical household records or report a point estimate from unsupported independence assumptions.

## Deliverable

Write a source-cited feasibility note to `docs/research/nz-tax-cost-data-feasibility.md`, including table identifiers/links, schemas checked, data limitations, and a clear go/no-go recommendation for aggregate costing.

## Resolution

The source-cited note is recorded in [`docs/research/nz-tax-cost-data-feasibility.md`](../../../docs/research/nz-tax-cost-data-feasibility.md). The reviewed official public releases provide useful separate age, wage-band, and taxable-income summaries, but no verified recurring joint distribution of age, qualifying PAYE earnings, other taxable income, and tax liability. The IRD XLSX workbooks could not be retrieved and inspected at worksheet level, so hidden or undocumented cross-tabs remain unverified. **No-go for an aggregate point estimate or data-only uncertainty interval from the currently verified tables.** Implement the exact individual calculator; report aggregate revenue as not estimable unless workbook inspection or a new release supplies adequate joint data. Do not infer a causal or behavioural policy effect from static calculations or forecast performance.
