# 0003. DuckDB and Parquet data store with full provenance

Status: Accepted
Date: 2026-10-29
Sources: DEC-003, `DATA_CATALOG.md` (ingestion rules)

## Context

Backtests are only valid if they can reproduce what was known at each forecast origin. Source agencies revise published values, and their current downloads are mutable latest vintages.

## Decision

Use DuckDB and Parquet as the initial research store. Retain original source files unchanged as versioned datasets, with:

- retrieval timestamp, publication timestamp, and reference period;
- publication vintage and revision history;
- URL, source series/table identifier, SHA-256 checksum, media type, and licence (the `SourceSnapshot` record);
- complete provenance from raw file to parsed observation.

Historical backtests may use only information available at each simulated forecast date. Version the bytes, not only the parsed values.

## Consequences

- Reads go through a point-in-time interface (`ObservationStore.as_of`) that never returns a value published after the requested time.
- A mutable "latest" download is never the sole vintage source, and an undocumented scrape is never the only ingestion path (`DATA_CATALOG.md`, ADR 0004).
- Raw snapshots and the DuckDB file are reproducible artefacts, not source, and are git-ignored (`data/raw/`, `data/store/`, `data/*.duckdb`).
- Source licences are recorded per snapshot, since general agency terms do not cover third-party data.
- Storage is a single-process research store; scaling or sharing it later would need a new decision.
