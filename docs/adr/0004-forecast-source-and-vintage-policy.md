# 0004. Forecast source of record and vintage policy

Status: Accepted
Date: 2026-10-29
Sources: DEC-004, `VALIDATION_PLAN.md`, `DATA_CATALOG.md`

## Context

Complete machine-readable historical vintages are not established for all three targets. Stats NZ revises GDP and HLFS seasonally adjusted estimates, so a backtest on today's revised series is not a real-time backtest.

## Decision

- Source of record is Stats NZ's official quarterly national series: seasonally adjusted chain-volume GDP, the all-groups CPI index, and the seasonally adjusted HLFS unemployment rate. At ingestion, record and verify table/series identifiers, units, seasonal-adjustment status, release date, and definition metadata.
- Preserve every retrieved release file unchanged with its provenance (ADR 0003). Prefer official release downloads and documented APIs.
- A historical origin is eligible for the strict real-time track (`VintageTrack.REAL_TIME`) only if each input value is tied to an official publication available by that origin's timestamp, using the release calendar and dated release rather than an assumed lag. Keep first-release outcomes separate from outcomes in a named later vintage.
- Where vintages cannot be reconstructed, run a separately labelled pseudo-out-of-sample track (`VintageTrack.PSEUDO_OOS`), disclose its vintage limitation, and never call it real-time. Begin prospective immutable snapshot capture so later evaluation can satisfy the strict track.
- A common-origin comparison issues after the latest of the three target releases for the shared reference quarter. Each forecast record carries the exact latest target quarter and publication timestamp. Common-origin and per-series operational-origin scores are never silently pooled.

## Consequences

- The backtest fails closed when a required historical vintage is absent.
- Results always state which vintage standard they satisfy; the two tracks are never pooled.
- Early evaluation will largely be on the pseudo-out-of-sample track until enough snapshots accumulate.
- This governs predictive evaluation only and establishes no causal policy validity.
