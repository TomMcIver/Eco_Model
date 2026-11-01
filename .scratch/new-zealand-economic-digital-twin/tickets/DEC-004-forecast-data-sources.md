# Choose forecast source-of-record and vintage policy

Status: closed
Type: grilling
Blocked by: 002-nz-data-catalog.md; 004-point-in-time-validation.md; 006-forecast-contract.md

## Question

Which source-of-record and vintage policy should the first quarterly forecast backtest use for real GDP growth, CPI inflation, and unemployment, given that historical machine-readable vintages are incomplete or unverified?

## Resolution

- Use Stats NZ's official quarterly national series as the source of record for all three targets: seasonally adjusted chain-volume GDP, the all-groups CPI index, and the seasonally adjusted HLFS unemployment rate. At ingestion, record and verify the exact table/series identifiers, units, seasonal-adjustment status, release date, and definition metadata; do not rely on copied series without a documented mapping.
- Preserve every retrieved release file unchanged with its URL, retrieval timestamp, publication timestamp, reference period, source identifier, checksum, and parsed-data version. Prefer official release downloads and documented APIs. Do not make an undocumented scrape or a mutable latest-series download the sole vintage source.
- A historical origin is eligible for a strict real-time track only when each input value can be tied to an official publication available by that origin's timestamp. Use the release calendar and dated release, not an assumed lag. Keep first-release outcomes separate from outcomes in a named later vintage.
- Where complete historical vintages cannot be reconstructed, use a separately labelled revised-data or pseudo-out-of-sample track, disclose its vintage limitation, and do not call it real-time. Begin prospective immutable snapshot capture so later evaluation can satisfy the strict track.
- For a common-origin comparison, issue after the latest of the three target releases for the shared reference quarter; use the exact latest available target quarter and publication timestamp in each forecast record. Do not silently pool common-origin and per-series operational-origin scores.

This source and vintage policy governs predictive evaluation only. It does not establish causal policy validity.
