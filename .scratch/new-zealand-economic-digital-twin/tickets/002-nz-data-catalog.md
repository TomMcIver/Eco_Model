# Research public New Zealand economic data and vintages

Status: closed
Type: research
Blocked by: none

## Question

Which official, publicly accessible, programmatically obtainable New Zealand datasets can support quarterly real GDP growth, CPI inflation, and unemployment forecasts and the wider initial state representation? Investigate Stats NZ, RBNZ, Treasury, IRD, MSD, MBIE, Education, OECD, IMF, World Bank, and ILO. For each relevant series, verify source URL, licensing/access, coverage, frequency and lag, geography/demographic detail, units/seasonality, missingness, revisions, vintage availability, and programmatic access. Clearly distinguish public data from restricted IDI or other microdata.

Prioritise initial target series, income/employment distributions relevant to tax costing, and point-in-time history. State where official sources do not provide vintage archives or APIs; never infer availability.

## Deliverable

Write a source-cited catalog to `DATA_CATALOG.md` in the repository root. Label unverified or inaccessible facts and give retrieval dates.

## Resolution

Research is recorded in [`DATA_CATALOG.md`](../../../DATA_CATALOG.md). Official public sources cover the target series and offer useful age, income, and tax aggregates; source vintage and programmatic history are uneven. Stats NZ IDI remains restricted microdata. The sources reviewed do not establish a recurring joint age-under-25, qualifying-employment-income, and other-income distribution adequate for a precise aggregate exemption cost. Inspect individual source tables before deciding whether bounded grouped-data estimates are feasible.

